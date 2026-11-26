"""STAC API

The catalog is also published through a STAC API, a standard interface for discovering
geospatial data, which exposes only published projects, survey missions and
survey-related records.
"""

import json
import urllib.parse

import pytest
import pytest_asyncio
import shapely
import shapely.geometry
import sqlmodel
from geoalchemy2.shape import from_shape
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.db.commands import projects as project_commands
from seis_lab_data.schemas import identifiers
from seis_lab_data.webapp.stacapi import conformance

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def draft_project(db, db_session_maker):
    """Create a draft project with no survey missions."""
    import uuid

    from seis_lab_data.schemas import projects as project_schemas

    to_create = project_schemas.ProjectCreate(
        id=identifiers.ProjectId(uuid.uuid4()),
        name="a draft project",
        description="draft",
    )
    async with db_session_maker() as session:
        project = await project_commands.create_project(session, to_create)
    yield project


@pytest_asyncio.fixture
async def sample_asset(db_session_maker, published_sample_data):
    """Add a GeoTIFF data asset to the first published record, yielding the asset and
    the record.
    """
    record = published_sample_data["records"][0]
    asset = models.RecordAsset(
        name="a data file",
        description="a description",
        survey_related_record_id=record.id,
        relative_path="some/file.tif",
        media_type="image/tiff",
        asset_type=[constants.AssetType.DATA],
    )
    async with db_session_maker() as session:
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
    yield asset, record


def test_landing_page(stac_api_client: TestClient):
    """The STAC API landing page describes the catalog, lists the standards it conforms
    to and links to its conformance declaration, search, collections and child catalogs.
    """
    response = stac_api_client.get("/stac/")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Catalog"
    assert body["conformsTo"] == conformance.CONFORMS_TO
    rels = {link["rel"] for link in body["links"]}
    assert {"self", "root", "conformance", "search", "data", "children"} <= rels


def test_landing_page_and_api_description_state_system_version(
    stac_api_client: TestClient, settings
):
    """The STAC API landing page and the description of the API both state the version
    of the system.
    """
    landing_page = stac_api_client.get("/stac/").json()
    assert landing_page["seis_lab_data:version"] == settings.version
    api_description = stac_api_client.get("/stac/openapi.json").json()
    assert api_description["info"]["version"] == settings.version


def test_api_description_documents_every_endpoint(stac_api_client: TestClient):
    """The description of the STAC API gives every endpoint a title, a description
    and a group, describes every parameter, and contains no empty contact or license
    details.
    """
    api_description = stac_api_client.get("/stac/openapi.json").json()
    assert "contact" not in api_description["info"]
    assert "license" not in api_description["info"]
    assert all(tag["name"] for tag in api_description["tags"])
    for path, operations in api_description["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), (method, path)
            assert operation.get("description"), (method, path)
            assert operation.get("tags"), (method, path)
            for parameter in operation.get("parameters", []):
                assert parameter.get("description"), (method, path, parameter)


def test_conformance(stac_api_client: TestClient):
    """The STAC API lists the standards it conforms to."""
    response = stac_api_client.get("/stac/conformance")
    assert response.status_code == 200
    assert response.json()["conformsTo"] == conformance.CONFORMS_TO


def test_children_lists_only_published_projects(
    stac_api_client: TestClient, published_sample_data, draft_project
):
    """The top level of the STAC API lists published projects but not draft ones."""
    response = stac_api_client.get("/stac/children")
    assert response.status_code == 200
    body = response.json()
    ids = {child["id"] for child in body["children"]}
    assert str(published_sample_data["projects"][0].id) in ids
    assert str(draft_project.id) not in ids


def test_project_catalog_published(stac_api_client: TestClient, published_sample_data):
    """A published project is available as a STAC catalog, with links to itself, to the
    root catalog, to its parent and to its children.
    """
    project = published_sample_data["projects"][0]
    response = stac_api_client.get(f"/stac/catalogs/{project.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(project.id)
    rels = {link["rel"] for link in body["links"]}
    assert {"self", "root", "parent", "children"} <= rels


def test_project_catalog_draft_is_404(stac_api_client: TestClient, draft_project):
    """A draft project is not available through the STAC API."""
    response = stac_api_client.get(f"/stac/catalogs/{draft_project.id}")
    assert response.status_code == 404


def test_project_catalog_missing_is_404(stac_api_client: TestClient, db):
    """A project that does not exist is reported as not found by the STAC API."""
    import uuid

    response = stac_api_client.get(f"/stac/catalogs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_project_children_lists_missions(
    stac_api_client: TestClient, published_sample_data
):
    """The STAC catalog of a project lists its survey missions as children."""
    project = published_sample_data["projects"][0]
    response = stac_api_client.get(f"/stac/catalogs/{project.id}/children")
    assert response.status_code == 200
    body = response.json()
    ids = {child["id"] for child in body["children"]}
    expected = {
        str(m.id)
        for m in published_sample_data["missions"]
        if m.project_id == project.id
    }
    assert expected <= ids


def test_collections_lists_published_missions(
    stac_api_client: TestClient, published_sample_data
):
    """Published survey missions are listed as STAC collections."""
    response = stac_api_client.get("/stac/collections")
    assert response.status_code == 200
    body = response.json()
    ids = {c["id"] for c in body["collections"]}
    assert str(published_sample_data["missions"][0].id) in ids


def test_collection_detail_published(
    stac_api_client: TestClient, published_sample_data
):
    """A published survey mission is available as a STAC collection, including its
    spatial extent.
    """
    mission = published_sample_data["missions"][0]
    response = stac_api_client.get(f"/stac/collections/{mission.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(mission.id)
    assert body["type"] == "Collection"
    assert body["extent"]["spatial"]["bbox"]


def test_collection_items_lists_published_records(
    stac_api_client: TestClient, published_sample_data
):
    """The STAC collection of a survey mission lists its published survey-related
    records as items.
    """
    mission = published_sample_data["missions"][0]
    response = stac_api_client.get(f"/stac/collections/{mission.id}/items")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    expected = {
        str(r.id)
        for r in published_sample_data["records"]
        if r.survey_mission_id == mission.id
    }
    ids = {f["id"] for f in body["features"]}
    assert expected <= ids


def test_item_detail_published(stac_api_client: TestClient, published_sample_data):
    """A published survey-related record is available as a STAC item belonging to the
    collection of its survey mission.
    """
    record = published_sample_data["records"][0]
    mission_id = record.survey_mission_id
    response = stac_api_client.get(f"/stac/collections/{mission_id}/items/{record.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(record.id)
    assert body["type"] == "Feature"
    assert body["collection"] == str(mission_id)


def test_items_name_their_dataset_category_and_workflow_stage(
    stac_api_client: TestClient, published_sample_data, sync_db_engine
):
    """The STAC item of a survey-related record states the name of its dataset category
    and of its workflow stage, along with their identifiers, both when the record is
    requested on its own and when it is found by a search.
    """
    record = published_sample_data["records"][0]
    with sqlmodel.Session(sync_db_engine) as session:
        db_record = session.get(models.SurveyRelatedRecord, record.id)
        expected = {
            "sld:dataset_category_id": str(db_record.dataset_category.id),
            "sld:dataset_category_name": db_record.dataset_category.name,
            "sld:workflow_stage_id": str(db_record.workflow_stage.id),
            "sld:workflow_stage_name": db_record.workflow_stage.name,
        }

    item_response = stac_api_client.get(
        f"/stac/collections/{record.survey_mission_id}/items/{record.id}"
    )
    search_response = stac_api_client.get(
        "/stac/search", params={"ids": str(record.id)}
    )

    assert item_response.status_code == 200
    assert search_response.status_code == 200
    for item in (item_response.json(), search_response.json()["features"][0]):
        properties = item["properties"]
        assert {key: properties.get(key) for key in expected} == expected


def test_item_detail_wrong_mission_is_404(
    stac_api_client: TestClient, published_sample_data
):
    """A survey-related record is reported as not found when requested from the
    collection of a survey mission it does not belong to.
    """
    record = published_sample_data["records"][0]
    other_mission = next(
        m for m in published_sample_data["missions"] if m.id != record.survey_mission_id
    )
    response = stac_api_client.get(
        f"/stac/collections/{other_mission.id}/items/{record.id}"
    )
    assert response.status_code == 404


def test_search_get_by_ids(stac_api_client: TestClient, published_sample_data):
    """A STAC API search by identifier returns exactly the requested survey-related
    record.
    """
    record = published_sample_data["records"][0]
    response = stac_api_client.get("/stac/search", params={"ids": str(record.id)})
    assert response.status_code == 200
    body = response.json()
    assert {f["id"] for f in body["features"]} == {str(record.id)}


def test_search_get_by_collections(stac_api_client: TestClient, published_sample_data):
    """A STAC API search by collection returns the survey-related records of the
    requested survey mission.
    """
    mission = published_sample_data["missions"][0]
    response = stac_api_client.get(
        "/stac/search", params={"collections": str(mission.id), "limit": 100}
    )
    assert response.status_code == 200
    body = response.json()
    expected = {
        str(r.id)
        for r in published_sample_data["records"]
        if r.survey_mission_id == mission.id
    }
    ids = {f["id"] for f in body["features"]}
    assert expected <= ids


def test_search_post_by_ids(stac_api_client: TestClient, published_sample_data):
    """A STAC API search by identifier also returns exactly the requested survey-related
    record when the search criteria are submitted in the body of the request.
    """
    record = published_sample_data["records"][0]
    response = stac_api_client.post("/stac/search", json={"ids": [str(record.id)]})
    assert response.status_code == 200
    body = response.json()
    assert {f["id"] for f in body["features"]} == {str(record.id)}


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_search_by_geometry_keeps_it_across_pages(
    stac_api_client: TestClient, published_sample_data, sync_db_engine, method
):
    """When a STAC API search by geometry is spread over several pages, the link to
    the following page keeps the geometry, so that the following page only contains
    the survey-related records within it as well.
    """
    with sqlmodel.Session(sync_db_engine) as session:
        for record in published_sample_data["records"]:
            db_record = session.get(models.SurveyRelatedRecord, record.id)
            db_record.bbox_4326 = from_shape(
                shapely.box(-9.5, 38.5, -9.0, 39.0), srid=4326
            )
            session.add(db_record)
        session.commit()
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-10, 38], [-8, 38], [-8, 40], [-10, 40], [-10, 38]]],
    }
    if method == "GET":
        response = stac_api_client.get(
            "/stac/search", params={"intersects": json.dumps(geometry), "limit": 1}
        )
    else:
        response = stac_api_client.post(
            "/stac/search", json={"intersects": geometry, "limit": 1}
        )
    assert response.status_code == 200
    first_page = response.json()
    assert first_page["numberMatched"] == len(published_sample_data["records"])

    next_link = next(li for li in first_page["links"] if li["rel"] == "next")
    next_url = urllib.parse.urlsplit(next_link["href"])
    next_query = urllib.parse.parse_qs(next_url.query)
    assert shapely.geometry.shape(json.loads(next_query["intersects"][0])).equals(
        shapely.geometry.shape(geometry)
    )
    next_response = stac_api_client.get(f"{next_url.path}?{next_url.query}")
    assert next_response.status_code == 200
    returned_ids = [
        feature["id"]
        for page in (first_page, next_response.json())
        for feature in page["features"]
    ]
    assert sorted(returned_ids) == sorted(
        str(r.id) for r in published_sample_data["records"]
    )


def test_asset_href_points_at_download_route(stac_api_client: TestClient, sample_asset):
    """Each file of a survey-related record appears in its STAC item with a link to
    download it from the catalog, along with its role and its media type.
    """
    asset, record = sample_asset
    mission_id = record.survey_mission_id
    response = stac_api_client.get(f"/stac/collections/{mission_id}/items/{record.id}")
    assert response.status_code == 200
    body = response.json()
    stac_asset = body["assets"][str(asset.id)]
    assert stac_asset["href"] == (
        f"http://testserver/survey-related-records/{record.id}"
        f"/assets/{asset.id}/download"
    )
    assert stac_asset["roles"] == [constants.AssetType.DATA.value]
    assert stac_asset["type"] == asset.media_type


@pytest_asyncio.fixture
async def sample_shapefile_asset(db_session_maker, published_sample_data):
    """Add a shapefile data asset to the first published record, yielding the asset and
    the record.
    """
    record = published_sample_data["records"][0]
    asset = models.RecordAsset(
        name="a shapefile",
        survey_related_record_id=record.id,
        relative_path="some/FOO.shp",
        media_type="application/prs.ipma.shp",
        asset_type=[constants.AssetType.DATA],
    )
    async with db_session_maker() as session:
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
    yield asset, record


def test_shapefile_asset_type_is_zip(
    stac_api_client: TestClient, sample_shapefile_asset
):
    """Shapefiles are offered by the STAC API as ZIP archives."""
    asset, record = sample_shapefile_asset
    response = stac_api_client.get(
        f"/stac/collections/{record.survey_mission_id}/items/{record.id}"
    )
    assert response.status_code == 200
    assert response.json()["assets"][str(asset.id)]["type"] == "application/zip"
