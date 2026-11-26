import logging
import uuid
from typing import Annotated

import stac_pydantic.api as stac_api
from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    Request,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.responses import JSONResponse

from ... import config
from ...operations import projects as project_ops
from ...operations import surveymissions as survey_mission_ops
from ...operations import surveyrelatedrecords as survey_related_record_ops
from ...schemas import identifiers
from . import (
    conformance,
    paging,
    serialization,
)
from . import links as link_helpers
from . import schemas as stac_schemas
from .dependencies import (
    SessionDep,
    SettingsDep,
)
from .responses import ERROR_RESPONSES

logger = logging.getLogger(__name__)
router = APIRouter()

# descriptions of the query parameters shared by several endpoints, for the OpenAPI
# document
_PAGE_DESCRIPTION = "Number of the page of results to return, starting at 1."
_LIMIT_DESCRIPTION = (
    "Maximum number of results per page. Defaults to the page size of the "
    "application, and is capped at 10000."
)
_BBOX_DESCRIPTION = (
    "Bounding box in EPSG:4326, as `minx,miny,maxx,maxy` (a 6 value bounding box "
    "is accepted, its vertical values are ignored). Only the items whose geometry "
    "intersects it are returned."
)
_DATETIME_DESCRIPTION = (
    "Date-time or interval, in RFC 3339 format, such as `2024-06-01T00:00:00Z` or "
    "`2024-01-01T00:00:00Z/2024-12-31T23:59:59Z`. Intervals may be open at one end "
    "with `..`. Only the items whose temporal extent overlaps it are returned. Only "
    "the date part of the values is taken into account."
)


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def _parse_id_list(raw: list[str] | None, id_type):
    if not raw:
        return None
    try:
        return [id_type(uuid.UUID(v)) for v in raw]
    except ValueError as err:
        raise HTTPException(400, f"Invalid id in {raw!r}: {err}") from err


@router.get(
    "/",
    name="landing-page",
    summary="Landing page",
    tags=["Core"],
    responses=ERROR_RESPONSES,
)
async def landing_page(request: Request, settings: SettingsDep) -> JSONResponse:
    """Root catalog of the API, with links to its other endpoints."""
    page = stac_api.LandingPage(
        type="Catalog",
        id="seis-lab-data",
        title="SeisLabData STAC API",
        description="Marine survey data catalog",
        stac_version=conformance.STAC_VERSION,
        # not part of the STAC specification, which defines no field for the
        # version of the software serving the catalog
        **{"seis_lab_data:version": settings.version},
        conformsTo=conformance.CONFORMS_TO,
        links=[
            link_helpers.self_link(request, "landing-page"),
            link_helpers.root_link(request),
            link_helpers.build_link(request, "service-desc", "openapi"),
            link_helpers.build_link(
                request, "service-doc", "swagger_ui_html", media_type="text/html"
            ),
            link_helpers.build_link(request, "conformance", "conformance"),
            link_helpers.build_link(
                request, "search", "search-get", media_type="application/geo+json"
            ),
            link_helpers.build_link(request, "data", "collections"),
            link_helpers.children_link(request, "children"),
        ],
    )
    return JSONResponse(_dump(page))


@router.get(
    "/conformance",
    name="conformance",
    summary="Conformance classes",
    tags=["Core"],
    responses=ERROR_RESPONSES,
)
async def get_conformance() -> JSONResponse:
    """Conformance classes of the STAC API and OGC API - Features specifications
    implemented by the API.
    """
    return JSONResponse(_dump(stac_api.Conformance(conformsTo=conformance.CONFORMS_TO)))


@router.get(
    "/children",
    name="children",
    summary="List projects",
    tags=["Catalogs"],
    responses=ERROR_RESPONSES,
)
async def root_children(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    page: int = Query(1, ge=1, description=_PAGE_DESCRIPTION),
    limit: int | None = Query(None, description=_LIMIT_DESCRIPTION),
) -> JSONResponse:
    """Published projects, as the child catalogs of the root catalog."""
    page_size = paging.parse_limit_param(limit, settings.pagination_page_size)
    projects, total = await project_ops.list_projects(
        session, initiator=None, page=page, page_size=page_size, include_total=True
    )
    links = [
        link_helpers.self_link(request, "children"),
        link_helpers.root_link(request),
    ]
    next_link = paging.build_next_link(request, "children", page, page_size, total)
    if next_link:
        links.append(next_link)
    prev_link = paging.build_prev_link(request, "children", page, page_size)
    if prev_link:
        links.append(prev_link)
    return JSONResponse(
        {
            "children": [
                _dump(serialization.catalog_from_project(p, request)) for p in projects
            ],
            "links": [_dump(link) for link in links],
        }
    )


@router.get(
    "/catalogs/{project_id}",
    name="project-catalog",
    summary="Get a project",
    tags=["Catalogs"],
    responses=ERROR_RESPONSES,
)
async def project_catalog(
    project_id: Annotated[uuid.UUID, Path(description="Identifier of the project.")],
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    """Published project, as a catalog."""
    project = await project_ops.get_project(
        identifiers.ProjectId(project_id), None, session
    )
    if project is None:
        raise HTTPException(404)
    return JSONResponse(_dump(serialization.catalog_from_project(project, request)))


@router.get(
    "/catalogs/{project_id}/children",
    name="project-children",
    summary="List the survey missions of a project",
    tags=["Catalogs"],
    responses=ERROR_RESPONSES,
)
async def project_children(
    project_id: Annotated[uuid.UUID, Path(description="Identifier of the project.")],
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    page: int = Query(1, ge=1, description=_PAGE_DESCRIPTION),
    limit: int | None = Query(None, description=_LIMIT_DESCRIPTION),
) -> JSONResponse:
    """Published survey missions of a published project, as its child collections."""
    project = await project_ops.get_project(
        identifiers.ProjectId(project_id), None, session
    )
    if project is None:
        raise HTTPException(404)
    page_size = paging.parse_limit_param(limit, settings.pagination_page_size)
    missions, total = await survey_mission_ops.list_survey_missions(
        session,
        initiator=None,
        project_id=identifiers.ProjectId(project_id),
        page=page,
        page_size=page_size,
        include_total=True,
    )
    path_params = {"project_id": project_id}
    links = [
        link_helpers.self_link(request, "project-children", **path_params),
        link_helpers.root_link(request),
    ]
    next_link = paging.build_next_link(
        request, "project-children", page, page_size, total, path_params=path_params
    )
    if next_link:
        links.append(next_link)
    prev_link = paging.build_prev_link(
        request, "project-children", page, page_size, path_params=path_params
    )
    if prev_link:
        links.append(prev_link)
    return JSONResponse(
        {
            "children": [
                _dump(serialization.collection_from_survey_mission(m, request))
                for m in missions
            ],
            "links": [_dump(link) for link in links],
        }
    )


@router.get(
    "/collections",
    name="collections",
    summary="List survey missions",
    tags=["Collections"],
    responses=ERROR_RESPONSES,
)
async def list_collections(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    page: int = Query(1, ge=1, description=_PAGE_DESCRIPTION),
    limit: int | None = Query(None, description=_LIMIT_DESCRIPTION),
) -> JSONResponse:
    """Published survey missions of all projects, as collections."""
    page_size = paging.parse_limit_param(limit, settings.pagination_page_size)
    missions, total = await survey_mission_ops.list_survey_missions(
        session, initiator=None, page=page, page_size=page_size, include_total=True
    )
    links = [
        link_helpers.self_link(request, "collections"),
        link_helpers.root_link(request),
    ]
    next_link = paging.build_next_link(request, "collections", page, page_size, total)
    if next_link:
        links.append(next_link)
    prev_link = paging.build_prev_link(request, "collections", page, page_size)
    if prev_link:
        links.append(prev_link)
    body = stac_api.Collections(
        collections=[
            serialization.collection_from_survey_mission(m, request) for m in missions
        ],
        links=links,
        numberMatched=total,
        numberReturned=len(missions),
    )
    return JSONResponse(_dump(body))


@router.get(
    "/collections/{mission_id}",
    name="collection",
    summary="Get a survey mission",
    tags=["Collections"],
    responses=ERROR_RESPONSES,
)
async def get_collection(
    mission_id: Annotated[
        uuid.UUID, Path(description="Identifier of the survey mission.")
    ],
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    """Published survey mission, as a collection."""
    mission = await survey_mission_ops.get_survey_mission(
        identifiers.SurveyMissionId(mission_id), None, session
    )
    if mission is None:
        raise HTTPException(404)
    return JSONResponse(
        _dump(serialization.collection_from_survey_mission(mission, request))
    )


@router.get(
    "/collections/{mission_id}/items",
    name="collection-items",
    summary="List the survey-related records of a survey mission",
    tags=["Collections"],
    responses=ERROR_RESPONSES,
)
async def collection_items(
    mission_id: Annotated[
        uuid.UUID, Path(description="Identifier of the survey mission.")
    ],
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    bbox: str | None = Query(None, description=_BBOX_DESCRIPTION),
    datetime: str | None = Query(None, description=_DATETIME_DESCRIPTION),
    page: int = Query(1, ge=1, description=_PAGE_DESCRIPTION),
    limit: int | None = Query(None, description=_LIMIT_DESCRIPTION),
) -> JSONResponse:
    """Published survey-related records of a published survey mission, as items,
    optionally filtered by their spatial and temporal extents.
    """
    mission = await survey_mission_ops.get_survey_mission(
        identifiers.SurveyMissionId(mission_id), None, session
    )
    if mission is None:
        raise HTTPException(404)
    page_size = paging.parse_limit_param(limit, settings.pagination_page_size)
    records, total = await survey_related_record_ops.list_survey_related_records(
        session,
        initiator=None,
        survey_mission_ids=[identifiers.SurveyMissionId(mission_id)],
        spatial_intersect=paging.parse_bbox_param(bbox),
        temporal_extent=paging.parse_datetime_param(datetime),
        page=page,
        page_size=page_size,
        include_total=True,
    )
    items = [
        serialization.item_from_survey_related_record(r, mission, request)
        for r in records
    ]
    extra_params = {}
    if bbox:
        extra_params["bbox"] = bbox
    if datetime:
        extra_params["datetime"] = datetime
    path_params = {"mission_id": mission_id}
    links = [
        link_helpers.self_link(
            request,
            "collection-items",
            media_type="application/geo+json",
            **path_params,
        ),
        link_helpers.root_link(request),
        link_helpers.collection_link(request, mission_id),
    ]
    next_link = paging.build_next_link(
        request,
        "collection-items",
        page,
        page_size,
        total,
        path_params=path_params,
        extra_params=extra_params,
    )
    if next_link:
        links.append(next_link)
    prev_link = paging.build_prev_link(
        request,
        "collection-items",
        page,
        page_size,
        path_params=path_params,
        extra_params=extra_params,
    )
    if prev_link:
        links.append(prev_link)
    body = stac_api.ItemCollection(
        type="FeatureCollection",
        features=items,
        links=links,
        numberMatched=total,
        numberReturned=len(items),
    )
    return JSONResponse(_dump(body), media_type="application/geo+json")


@router.get(
    "/collections/{mission_id}/items/{item_id}",
    name="item",
    summary="Get a survey-related record",
    tags=["Collections"],
    responses=ERROR_RESPONSES,
)
async def get_item(
    mission_id: Annotated[
        uuid.UUID, Path(description="Identifier of the survey mission.")
    ],
    item_id: Annotated[
        uuid.UUID, Path(description="Identifier of the survey-related record.")
    ],
    request: Request,
    session: SessionDep,
) -> JSONResponse:
    """Published survey-related record, as an item."""
    result = await survey_related_record_ops.get_survey_related_record(
        identifiers.SurveyRelatedRecordId(item_id), None, session
    )
    if result is None:
        raise HTTPException(404)
    record, _related_to, _subject_for = result
    if record.survey_mission_id != mission_id:
        raise HTTPException(404)
    item = serialization.item_from_survey_related_record(
        record, record.survey_mission, request
    )
    return JSONResponse(_dump(item), media_type="application/geo+json")


async def _execute_search(
    request: Request,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    *,
    collections: list[str] | None,
    ids: list[str] | None,
    bbox_raw: str | None,
    datetime_raw: str | None,
    intersects_raw: str | None,
    limit: int | None,
    page: int,
    self_route_name: str,
) -> JSONResponse:
    page_size = paging.parse_limit_param(limit, settings.pagination_page_size)
    spatial_intersect = paging.parse_intersects_param(
        intersects_raw
    ) or paging.parse_bbox_param(bbox_raw)
    records, total = await survey_related_record_ops.list_survey_related_records(
        session,
        initiator=None,
        survey_mission_ids=_parse_id_list(collections, identifiers.SurveyMissionId),
        record_ids=_parse_id_list(ids, identifiers.SurveyRelatedRecordId),
        spatial_intersect=spatial_intersect,
        temporal_extent=paging.parse_datetime_param(datetime_raw),
        page=page,
        page_size=page_size,
        include_total=True,
    )
    items = [
        serialization.item_from_survey_related_record(r, r.survey_mission, request)
        for r in records
    ]
    extra_params = {}
    if collections:
        extra_params["collections"] = ",".join(collections)
    if ids:
        extra_params["ids"] = ",".join(ids)
    if datetime_raw:
        extra_params["datetime"] = datetime_raw
    if bbox_raw:
        extra_params["bbox"] = bbox_raw
    if intersects_raw:
        extra_params["intersects"] = intersects_raw
    links = [
        link_helpers.self_link(
            request, self_route_name, media_type="application/geo+json"
        ),
        link_helpers.root_link(request),
    ]
    next_link = paging.build_next_link(
        request, "search-get", page, page_size, total, extra_params=extra_params
    )
    if next_link:
        links.append(next_link)
    prev_link = paging.build_prev_link(
        request, "search-get", page, page_size, extra_params=extra_params
    )
    if prev_link:
        links.append(prev_link)
    body = stac_api.ItemCollection(
        type="FeatureCollection",
        features=items,
        links=links,
        numberMatched=total,
        numberReturned=len(items),
    )
    return JSONResponse(_dump(body), media_type="application/geo+json")


@router.get(
    "/search",
    name="search-get",
    summary="Search items",
    tags=["Item search"],
    responses=ERROR_RESPONSES,
)
async def search_get(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    bbox: str | None = Query(
        None, description=_BBOX_DESCRIPTION + " Excludes `intersects`."
    ),
    intersects: str | None = Query(
        None,
        description=(
            "GeoJSON geometry, in EPSG:4326. Only the items whose geometry intersects "
            "it are returned. Excludes `bbox`."
        ),
    ),
    datetime: str | None = Query(None, description=_DATETIME_DESCRIPTION),
    collections: str | None = Query(
        None,
        description=(
            "Comma-separated identifiers of the survey missions to search in."
        ),
    ),
    ids: str | None = Query(
        None,
        description="Comma-separated identifiers of the survey-related records to return.",
    ),
    limit: int | None = Query(None, description=_LIMIT_DESCRIPTION),
    page: int = Query(1, ge=1, description=_PAGE_DESCRIPTION),
) -> JSONResponse:
    """Published survey-related records of all survey missions, as items, filtered
    by the given criteria, which must all be met.
    """
    if bbox is not None and intersects is not None:
        raise HTTPException(400, "bbox and intersects are mutually exclusive")
    return await _execute_search(
        request,
        session,
        settings,
        collections=collections.split(",") if collections else None,
        ids=ids.split(",") if ids else None,
        bbox_raw=bbox,
        datetime_raw=datetime,
        intersects_raw=intersects,
        limit=limit,
        page=page,
        self_route_name="search-get",
    )


@router.post(
    "/search",
    name="search-post",
    summary="Search items, with the criteria in the request body",
    tags=["Item search"],
    responses=ERROR_RESPONSES,
)
async def search_post(
    request: Request,
    search: stac_schemas.Search,
    session: SessionDep,
    settings: SettingsDep,
) -> JSONResponse:
    """Published survey-related records of all survey missions, as items, filtered
    by the criteria of the request body, which must all be met. The criteria are the
    same as those of the GET method, with `bbox`, `collections` and `ids` given as
    JSON arrays and `intersects` as a GeoJSON object.
    """
    # the criteria are passed on as the GET method's parameters, which the links to
    # the other pages of results carry
    intersects_raw = None
    bbox_raw = None
    if search.intersects is not None:
        intersects_raw = search.intersects.model_dump_json(exclude_none=True)
    elif search.bbox is not None:
        bbox_raw = ",".join(str(v) for v in search.bbox)
    return await _execute_search(
        request,
        session,
        settings,
        collections=search.collections,
        ids=search.ids,
        bbox_raw=bbox_raw,
        datetime_raw=search.datetime,
        intersects_raw=intersects_raw,
        limit=search.limit,
        page=search.page or 1,
        self_route_name="search-post",
    )
