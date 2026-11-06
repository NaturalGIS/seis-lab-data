"""Integration tests for when projects and survey missions get a new thumbnail.

The base map is out of reach in the tests, so the render itself is faked; the
renderer has its own tests in test_derivers.py.
"""

import inspect
import uuid

import pytest

from seis_lab_data import constants
from seis_lab_data.db.queries import (
    projects as project_queries,
    surveymissions as mission_queries,
)
from seis_lab_data.operations import (
    previews as preview_ops,
    projects as project_ops,
    surveymissions as mission_ops,
)
from seis_lab_data.schemas import (
    events as event_schemas,
    identifiers,
    projects as project_schemas,
    surveymissions as mission_schemas,
)
from seis_lab_data.tasks import previews as preview_tasks

_BBOX = "POLYGON((-10 38, -8 38, -8 40, -10 40, -10 38))"
_OTHER_BBOX = "POLYGON((-9 38, -8 38, -8 39, -9 39, -9 38))"
_THUMBNAIL = b"fake webp payload"


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


@pytest.fixture
def thumbnail_settings(settings, monkeypatch):
    monkeypatch.setattr(
        settings, "thumbnail_base_tile_layer_url", "http://tiles.invalid/{z}/{x}/{y}"
    )
    # the test settings have no message broker to dispatch the events through
    monkeypatch.setattr(settings, "_event_dispatcher", _EventCollector())
    monkeypatch.setattr(
        preview_ops.bbox_thumbnail,
        "render_bbox_thumbnail",
        lambda basemap_source, bbox_4326, style: _THUMBNAIL,
    )
    return settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_thumbnail_follows_the_bbox(
    db_session_maker, admin_user, thumbnail_settings, monkeypatch
):
    queued = []
    monkeypatch.setattr(
        preview_tasks.generate_project_thumbnail,
        "send",
        lambda **kwargs: queued.append(kwargs),
    )
    project_id = identifiers.ProjectId(uuid.uuid4())

    async def update(bbox_4326):
        async with db_session_maker() as session:
            await project_ops.update_project(
                request_id=identifiers.RequestId(uuid.uuid4()),
                project_id=project_id,
                to_update=project_schemas.ProjectUpdate(
                    description="An edited description", bbox_4326=bbox_4326
                ),
                initiator=admin_user,
                session=session,
                event_dispatcher=_EventCollector(),
            )

    async with db_session_maker() as session:
        await project_ops.create_project(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=project_schemas.ProjectCreate(
                id=project_id, name="A fake project", root_path="", bbox_4326=_BBOX
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
        )
    assert [message["raw_project_id"] for message in queued] == [str(project_id)]

    # unwrapped, as the actors only run inside a worker
    await inspect.unwrap(preview_tasks.generate_project_thumbnail.fn)(
        **queued[0], settings=thumbnail_settings
    )
    async with db_session_maker() as session:
        project = await project_queries.get_project(session, project_id)
        assert project.thumbnail == _THUMBNAIL
    event = thumbnail_settings.get_event_dispatcher().events[-1]
    assert (event.resource_type, event.resource_id, event.modification) == (
        constants.ResourceType.PROJECT,
        str(project_id),
        constants.ResourceModification.UPDATED,
    )

    # the update form sends the bbox back, changed or not
    await update(_BBOX)
    assert len(queued) == 1
    await update(_OTHER_BBOX)
    assert len(queued) == 2
    await update(None)
    assert len(queued) == 2
    async with db_session_maker() as session:
        project = await project_queries.get_project(session, project_id)
        assert project.thumbnail is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_survey_mission_thumbnail_follows_the_bbox(
    db_session_maker, admin_user, sample_projects, thumbnail_settings, monkeypatch
):
    queued = []
    monkeypatch.setattr(
        preview_tasks.generate_survey_mission_thumbnail,
        "send",
        lambda **kwargs: queued.append(kwargs),
    )
    survey_mission_id = identifiers.SurveyMissionId(uuid.uuid4())

    async def update(bbox_4326):
        async with db_session_maker() as session:
            await mission_ops.update_survey_mission(
                request_id=identifiers.RequestId(uuid.uuid4()),
                survey_mission_id=survey_mission_id,
                to_update=mission_schemas.SurveyMissionUpdate(
                    description="An edited description", bbox_4326=bbox_4326
                ),
                initiator=admin_user,
                session=session,
                event_dispatcher=_EventCollector(),
            )

    async with db_session_maker() as session:
        await mission_ops.create_survey_mission(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=mission_schemas.SurveyMissionCreate(
                id=survey_mission_id,
                project_id=identifiers.ProjectId(sample_projects[0].id),
                name="A fake survey mission",
                description="",
                relative_path="fake-mission",
                bbox_4326=_BBOX,
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
        )
    assert [message["raw_survey_mission_id"] for message in queued] == [
        str(survey_mission_id)
    ]

    # unwrapped, as the actors only run inside a worker
    await inspect.unwrap(preview_tasks.generate_survey_mission_thumbnail.fn)(
        **queued[0], settings=thumbnail_settings
    )
    async with db_session_maker() as session:
        survey_mission = await mission_queries.get_survey_mission(
            session, survey_mission_id
        )
        assert survey_mission.thumbnail == _THUMBNAIL
    event = thumbnail_settings.get_event_dispatcher().events[-1]
    assert (event.resource_type, event.resource_id, event.modification) == (
        constants.ResourceType.MISSION,
        str(survey_mission_id),
        constants.ResourceModification.UPDATED,
    )

    # the update form sends the bbox back, changed or not
    await update(_BBOX)
    assert len(queued) == 1
    await update(_OTHER_BBOX)
    assert len(queued) == 2
    await update(None)
    assert len(queued) == 2
    async with db_session_maker() as session:
        survey_mission = await mission_queries.get_survey_mission(
            session, survey_mission_id
        )
        assert survey_mission.thumbnail is None
