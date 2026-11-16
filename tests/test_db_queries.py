import datetime as dt
import uuid

import pytest
import pytest_asyncio
import shapely
import sqlalchemy

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.db.commands import projects as project_commands
from seis_lab_data.db.commands import surveymissions as mission_commands
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.db.queries import projects as project_queries
from seis_lab_data.db.queries import recordassets as asset_queries
from seis_lab_data.db.queries import surveymissions as mission_queries
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.schemas import filters as filter_schemas
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import projects as project_schemas


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_projects(sample_projects, db_session_maker):
    async with db_session_maker() as session:
        _projects, total = await project_queries.list_projects(
            session, include_total=True
        )
        assert total == len(sample_projects)


@pytest.mark.parametrize(
    "project_id_filter, expected_total",
    [
        pytest.param(None, 6),
        pytest.param(
            identifiers.ProjectId(uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3")), 3
        ),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_missions(
    sample_survey_missions, db_session_maker, project_id_filter, expected_total
):
    async with db_session_maker() as session:
        _survey_missions, total = await mission_queries.list_survey_missions(
            session, project_id=project_id_filter, include_total=True
        )
        assert total == expected_total


@pytest.mark.parametrize(
    "survey_mission_ids_filter, expected_total",
    [
        pytest.param(None, 2),
        pytest.param(
            [
                identifiers.SurveyMissionId(
                    uuid.UUID("cfe10cd8-5a5e-40e4-807b-7064f94a2edf")
                )
            ],
            1,
        ),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_related_records(
    sample_survey_related_records,
    db_session_maker,
    survey_mission_ids_filter,
    expected_total,
):
    async with db_session_maker() as session:
        _survey_records, total = await record_queries.list_survey_related_records(
            session, survey_mission_ids=survey_mission_ids_filter, include_total=True
        )
        assert total == expected_total


@pytest.mark.parametrize(
    "project_id_filter, expected_total",
    [
        pytest.param(None, 2),
        pytest.param(
            identifiers.ProjectId(uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3")), 2
        ),
        pytest.param(
            identifiers.ProjectId(uuid.UUID("8f931331-15c3-4899-846c-38470f6bcb5a")), 0
        ),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_related_records_project_id_filter(
    sample_survey_related_records,
    db_session_maker,
    project_id_filter,
    expected_total,
):
    async with db_session_maker() as session:
        _survey_records, total = await record_queries.list_survey_related_records(
            session, project_id=project_id_filter, include_total=True
        )
        assert total == expected_total


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_type_queries_ignore_derived_assets(
    sample_survey_related_records, db_session_maker
):
    # a preview's media type is an implementation detail: it must neither show
    # up in the media type datalist nor make its record match a search
    first_record, _second_record = sample_survey_related_records
    async with db_session_maker() as session:
        session.add(
            models.RecordAsset(
                id=uuid.uuid4(),
                name="A derived asset",
                description="",
                survey_related_record_id=first_record.id,
                media_type="image/webp",
                asset_type=[constants.AssetType.PREVIEW],
            )
        )
        await session.commit()

        media_types = await asset_queries.list_media_types(session)
        assert "image/webp" not in media_types
        # the media type the sample assets declare
        assert "application/octet-stream" in media_types
        assert await asset_queries.count_media_types(session) == len(media_types)

        _records, total = await record_queries.list_survey_related_records(
            session, asset_media_type_filter="image/webp", include_total=True
        )
        assert total == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_listing_records_does_not_load_derived_asset_payloads(
    sample_survey_related_records, db_session_maker
):
    # listings never show a preview image, so loading one per record would only
    # weigh their pages down
    first_record, _second_record = sample_survey_related_records
    async with db_session_maker() as session:
        session.add(
            models.RecordAsset(
                id=uuid.uuid4(),
                name="A derived asset",
                description="",
                survey_related_record_id=first_record.id,
                media_type="image/webp",
                asset_type=[constants.AssetType.PREVIEW],
                data=b"not a webp",
            )
        )
        await session.commit()

        records, _total = await record_queries.list_survey_related_records(session)
        listed = next(r for r in records if r.id == first_record.id)
        preview = next(
            a for a in listed.assets if constants.AssetType.PREVIEW in a.asset_type
        )
        assert "data" in sqlalchemy.inspect(preview).unloaded


@pytest_asyncio.fixture
async def extent_projects(db, db_session_maker):
    """Projects with assorted temporal and spatial extents, keyed by name."""
    to_create = {
        "spans 2020-2024": (dt.date(2020, 1, 1), dt.date(2024, 12, 31), None),
        "within 2022": (dt.date(2022, 3, 1), dt.date(2022, 6, 30), None),
        "ended 2019": (dt.date(2018, 1, 1), dt.date(2019, 12, 31), None),
        "begins 2025": (dt.date(2025, 1, 1), None, None),
        "open begin until 2021": (None, dt.date(2021, 1, 1), None),
        "since 2010, open end": (dt.date(2010, 1, 1), None, None),
        "no temporal extent": (None, None, None),
        "off portugal": (None, None, "POLYGON((-10 38, -8 38, -8 40, -10 40, -10 38))"),
        "off the azores": (
            None,
            None,
            "POLYGON((-29 37, -25 37, -25 40, -29 40, -29 37))",
        ),
    }
    async with db_session_maker() as session:
        for name, (begin, end, bbox_wkt) in to_create.items():
            await project_commands.create_project(
                session,
                project_schemas.ProjectCreate(
                    id=identifiers.ProjectId(uuid.uuid4()),
                    name=name,
                    temporal_extent_begin=begin,
                    temporal_extent_end=end,
                    bbox_4326=bbox_wkt,
                ),
            )
    return set(to_create)


@pytest.mark.parametrize(
    "begin, end, expected_names",
    [
        pytest.param(
            dt.date(2022, 1, 1),
            dt.date(2023, 12, 31),
            {
                "spans 2020-2024",
                "within 2022",
                "since 2010, open end",
                "no temporal extent",
            },
            id="overlapping_range",
        ),
        pytest.param(
            dt.date(2024, 6, 1),
            None,
            {
                "spans 2020-2024",
                "begins 2025",
                "since 2010, open end",
                "no temporal extent",
            },
            id="only_begin",
        ),
        pytest.param(
            None,
            dt.date(2019, 6, 1),
            {
                "ended 2019",
                "open begin until 2021",
                "since 2010, open end",
                "no temporal extent",
            },
            id="only_end",
        ),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_temporal_extent_filter_matches_overlapping_extents(
    extent_projects, db_session_maker, begin, end, expected_names
):
    # projects without a spatial extent are irrelevant here, but are always
    # matched by the temporal filter as they have no temporal extent either
    expected_names = expected_names | {"off portugal", "off the azores"}
    async with db_session_maker() as session:
        items, _ = await project_queries.list_projects(
            session,
            page_size=50,
            temporal_extent=filter_schemas.TemporalExtentFilterValue(
                begin=begin, end=end
            ),
        )
    assert {item.name for item in items} == expected_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_spatial_filter_keeps_items_without_a_spatial_extent(
    extent_projects, db_session_maker
):
    async with db_session_maker() as session:
        items, _ = await project_queries.list_projects(
            session,
            page_size=50,
            spatial_intersect=shapely.box(-11, 37, -7, 41),
        )
    assert {item.name for item in items} == extent_projects - {"off the azores"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_temporal_extent_filter_matches_overlapping_record_extents(
    sample_survey_related_records, db_session_maker
):
    first_record, second_record = sample_survey_related_records
    async with db_session_maker() as session:
        for record, begin, end in (
            (first_record, dt.date(2020, 1, 1), dt.date(2024, 12, 31)),
            (second_record, dt.date(2018, 1, 1), dt.date(2019, 12, 31)),
        ):
            db_record = await session.get(models.SurveyRelatedRecord, record.id)
            db_record.temporal_extent_begin = begin
            db_record.temporal_extent_end = end
            session.add(db_record)
        await session.commit()
        items, _ = await record_queries.list_survey_related_records(
            session,
            temporal_extent=filter_schemas.TemporalExtentFilterValue(
                begin=dt.date(2022, 1, 1), end=dt.date(2022, 12, 31)
            ),
        )
    assert [item.id for item in items] == [first_record.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_status_filter_of_projects(sample_projects, db_session_maker):
    draft_project, published_project, *_ = sample_projects
    async with db_session_maker() as session:
        await project_commands.set_project_status(
            session,
            identifiers.ProjectId(published_project.id),
            constants.ProjectStatus.PUBLISHED,
        )
        published, _ = await project_queries.list_projects(
            session, status=constants.ProjectStatus.PUBLISHED
        )
        drafts, _ = await project_queries.list_projects(
            session, status=constants.ProjectStatus.DRAFT
        )
        published_drafts, _ = await project_queries.list_published_projects(
            session, status=constants.ProjectStatus.DRAFT
        )
    assert [item.id for item in published] == [published_project.id]
    assert draft_project.id in {item.id for item in drafts}
    assert published_project.id not in {item.id for item in drafts}
    assert published_drafts == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_status_filter_of_survey_missions(
    sample_survey_missions, db_session_maker
):
    busy_mission = sample_survey_missions[0]
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session,
            identifiers.SurveyMissionId(busy_mission.id),
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
        )
        items, total = await mission_queries.list_survey_missions(
            session,
            status=constants.SurveyMissionStatus.UNDER_DISCOVERY,
            include_total=True,
        )
    assert [item.id for item in items] == [busy_mission.id]
    assert total == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_status_filter_of_survey_related_records(
    sample_survey_related_records, db_session_maker
):
    first_record, second_record = sample_survey_related_records
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session,
            identifiers.SurveyRelatedRecordId(first_record.id),
            constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
        )
        items, _ = await record_queries.list_survey_related_records(
            session, status=constants.SurveyRelatedRecordStatus.UNDER_EXPORT
        )
        matching_ids = (
            await session.exec(
                record_queries.build_survey_related_record_id_statement(
                    status=constants.SurveyRelatedRecordStatus.DRAFT
                )
            )
        ).all()
    assert [item.id for item in items] == [first_record.id]
    assert list(matching_ids) == [second_record.id]
