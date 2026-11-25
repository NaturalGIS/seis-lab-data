"""Live updates of pages

Pages showing projects, survey missions and survey-related records are updated while
they are open, as the statuses of entries change, as records are discovered in the file
archive and as record previews are generated, without the user reloading them.
"""

import json
import uuid

import jinja2
import pytest
from starlette_babel.contrib.jinja import configure_jinja_env

from seis_lab_data import (
    constants,
    subscribers,
)
from seis_lab_data.db.commands import projects as project_commands
from seis_lab_data.db.commands import surveymissions as mission_commands
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import messages as message_schemas
from seis_lab_data.schemas import user as user_schemas
from seis_lab_data.webapp.streamhandlers import common as common_handlers

# how the flash helpers show a notification right away, or store it for the next page
_SAME_PAGE_NOTIFICATION = "showFlash("
_STORED_NOTIFICATION = "localStorage.setItem('sld:flash'"

_USER = user_schemas.User(
    id=identifiers.UserId("some-user"), email="user@example.com", username="user"
)


def _status_changed(resource_type, resource_id, succeeded=True):
    return message_schemas.ResourceStatusChangedMessage(
        request_id=uuid.uuid4(),
        resource_type=resource_type,
        resource_id=str(resource_id),
        succeeded=succeeded,
        new_status=constants.SurveyRelatedRecordStatus.PUBLISHED.value,
    )


async def _collect(handler, message, context) -> list[str]:
    return [event async for event in handler(message, context)]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_resource_type",
    [
        pytest.param(constants.ResourceType.PROJECT, id="project-page"),
        pytest.param(constants.ResourceType.MISSION, id="mission-page"),
    ],
)
@pytest.mark.parametrize(
    "record_status, expected_busy",
    [
        pytest.param(
            constants.SurveyRelatedRecordStatus.UNDER_EXPORT, True, id="busy-record"
        ),
        pytest.param(
            constants.SurveyRelatedRecordStatus.DRAFT, False, id="idle-record"
        ),
    ],
)
async def test_detail_page_tracks_busy_records_without_notifying_them(
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    page_resource_type,
    record_status,
    expected_busy,
):
    """When the status of a record changes, the pages of its project and survey mission
    refresh their record listing and indicate whether any of their records is busy, such
    as under export, without showing a notification for each record.
    """
    record = sample_survey_related_records[0]
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session, identifiers.SurveyRelatedRecordId(record.id), record_status
        )
    resource_id = (
        record.survey_mission.project_id
        if page_resource_type == constants.ResourceType.PROJECT
        else record.survey_mission_id
    )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.RECORD, record.id),
        subscribers.HandlerContext(
            resource_id=str(resource_id),
            resource_type=page_resource_type,
            db_session_factory=db_session_maker,
            user=admin_user,
        ),
    )

    (signals,) = [_parse_patched_signals(event) for event in events]
    assert "listingVersion" in signals
    assert signals["hasBusyDescendants"] is expected_busy
    # tasks change the statuses of many records at once
    assert not any(_SAME_PAGE_NOTIFICATION in event for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_page_tracks_busy_missions(
    db_session_maker, sample_survey_missions, admin_user
):
    """When the status of a survey mission changes, the page of its project shows a
    notification and indicates that one of its survey missions is busy, such as under
    discovery.
    """
    mission = sample_survey_missions[0]
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session,
            identifiers.SurveyMissionId(mission.id),
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
        )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.MISSION, mission.id),
        subscribers.HandlerContext(
            resource_id=str(mission.project_id),
            resource_type=constants.ResourceType.PROJECT,
            db_session_factory=db_session_maker,
            user=admin_user,
        ),
    )

    assert any(_SAME_PAGE_NOTIFICATION in event for event in events)
    (signals,) = [
        _parse_patched_signals(event)
        for event in events
        if "hasBusyDescendants" in event
    ]
    assert signals["hasBusyDescendants"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "succeeded, expected_refreshes",
    [pytest.param(True, 1, id="succeeded"), pytest.param(False, 0, id="failed")],
)
async def test_list_page_quietly_refreshes_on_status_change(
    succeeded, expected_refreshes
):
    """A list page refreshes its listing, without showing a notification, when the
    status of an entry changes, and is left unchanged when the status change fails.
    """
    events = await _collect(
        common_handlers.handle_resource_status_changed_list_page,
        _status_changed(constants.ResourceType.RECORD, uuid.uuid4(), succeeded),
        subscribers.HandlerContext(),
    )

    assert len(events) == expected_refreshes
    assert all("listingVersion" in event for event in events)
    assert not any(_SAME_PAGE_NOTIFICATION in event for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "own_record, expected_refreshes",
    [pytest.param(True, 1, id="own-record"), pytest.param(False, 0, id="other-record")],
)
async def test_mission_page_refreshes_only_for_its_own_records(
    db_session_maker,
    sample_survey_related_records,
    sample_survey_missions,
    admin_user,
    own_record,
    expected_refreshes,
):
    """A survey mission page refreshes its record listing only when the status of one of
    its own records changes, and keeps no notification to be shown on a later page.
    """
    record = sample_survey_related_records[0]
    mission_id = (
        record.survey_mission_id
        if own_record
        else next(
            m.id for m in sample_survey_missions if m.id != record.survey_mission_id
        )
    )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.RECORD, record.id),
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            db_session_factory=db_session_maker,
            user=admin_user,
        ),
    )

    assert sum("listingVersion" in event for event in events) == expected_refreshes
    # the page is not reloaded, a notification stored for the next one would be
    # shown out of context, on whatever page the user visits next
    assert not any(_STORED_NOTIFICATION in event for event in events)


@pytest.mark.asyncio
async def test_record_page_refreshes_its_details_on_status_change():
    """When the status of a record changes, its page shows a notification and refreshes
    its details in place, without reloading.
    """
    record_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.RECORD, record_id),
        subscribers.HandlerContext(
            resource_id=str(record_id),
            resource_type=constants.ResourceType.RECORD,
        ),
    )

    # no reload: notified on the same page, whose details are then re-fetched
    assert len(events) == 2
    assert _SAME_PAGE_NOTIFICATION in events[0]
    assert "detailsVersion" in events[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "own_mission, expected_refreshes",
    [pytest.param(True, 1, id="own-mission"), pytest.param(False, 0, id="other")],
)
async def test_record_page_refreshes_its_details_on_its_mission_status_change(
    own_mission, expected_refreshes
):
    """A record page refreshes its details when the status of its own survey mission
    changes, and ignores the status changes of other survey missions.
    """
    mission_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(
            constants.ResourceType.MISSION, mission_id if own_mission else uuid.uuid4()
        ),
        subscribers.HandlerContext(
            resource_id=str(uuid.uuid4()),
            parent_resource_id=str(mission_id),
            resource_type=constants.ResourceType.RECORD,
        ),
    )

    assert len(events) == expected_refreshes
    assert all("detailsVersion" in event for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_status, resets_progress",
    [
        pytest.param(constants.SurveyMissionStatus.PUBLISHED, False, id="published"),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY, True, id="under-discovery"
        ),
    ],
)
async def test_mission_page_refreshes_in_place_on_status_change(
    new_status, resets_progress
):
    """When the status of a survey mission changes, its page shows a notification and
    updates its status, details and record listing in place, without reloading. When a
    discovery starts, the discovery progress shown on the page is also reset.
    """
    mission_id = uuid.uuid4()
    message = message_schemas.ResourceStatusChangedMessage(
        request_id=uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(mission_id),
        succeeded=True,
        new_status=new_status.value,
    )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        message,
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
        ),
    )

    # a reload would close the page's stream and lose the messages sent meanwhile
    assert len(events) == 2
    assert _SAME_PAGE_NOTIFICATION in events[0]
    assert not any("window.location" in event for event in events)
    for signal in ("status", "detailsVersion", "listingVersion"):
        assert signal in events[1]
    assert new_status.value in events[1]
    for signal in (
        "discoveryProgress",
        "discoverySectionsDone",
        "discoverySectionsTotal",
        "discoverySectionLabel",
        "discoverySectionPath",
    ):
        assert (signal in events[1]) is resets_progress


def _build_discovery_message(
    mission_id,
    modification,
    succeeded=True,
    details=None,
    request_id=None,
    **sections,
):
    return message_schemas.DiscoveryMessage(
        request_id=request_id or uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(mission_id),
        modification=modification,
        succeeded=succeeded,
        details=details,
        **sections,
    )


def _parse_patched_signals(event: str) -> dict:
    (data,) = [line for line in event.splitlines() if line.startswith("data: signals ")]
    return json.loads(data.removeprefix("data: signals "))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sections, expected",
    [
        pytest.param({}, None, id="sections unknown"),
        pytest.param(
            {"sections_done": 0, "sections_total": 3},
            {
                "discoverySectionsDone": 0,
                "discoverySectionsTotal": 3,
                "discoverySectionLabel": "sections to discover: 3",
                "discoverySectionPath": "",
            },
            id="no section reached yet",
        ),
        pytest.param(
            {
                "sections_done": 1,
                "sections_total": 3,
                "current_section": "s06-mbes/s02-raw-data",
            },
            {
                "discoverySectionsDone": 1,
                "discoverySectionsTotal": 3,
                "discoverySectionLabel": "section 2 of 3: s06-mbes/s02-raw-data",
                "discoverySectionPath": "s06-mbes/s02-raw-data",
            },
            id="short section path",
        ),
        pytest.param(
            {
                "sections_done": 2,
                "sections_total": 3,
                "current_section": "s06-mbes/s08-gis/s01-surfaces",
            },
            {
                "discoverySectionsDone": 2,
                "discoverySectionsTotal": 3,
                "discoverySectionLabel": "section 3 of 3: s06-mbes/…/s01-surfaces",
                "discoverySectionPath": "s06-mbes/s08-gis/s01-surfaces",
            },
            id="long section path elided",
        ),
    ],
)
async def test_mission_page_shows_discovery_sections(sections, expected):
    """During a discovery, the survey mission page shows which section of the file
    archive is being processed and how many sections there are, abbreviating long
    section paths, and shows no section details while their number is unknown.
    """
    mission_id = uuid.uuid4()

    (event,) = await _collect(
        common_handlers.handle_discovery_detail_page,
        _build_discovery_message(
            mission_id, constants.DiscoveryStage.PROGRESS, details="3 files", **sections
        ),
        subscribers.HandlerContext(
            resource_id=str(mission_id), resource_type=constants.ResourceType.MISSION
        ),
    )

    signals = _parse_patched_signals(event)
    if expected is None:
        assert not any(name.startswith("discoverySection") for name in signals)
    else:
        assert {
            name: value
            for name, value in signals.items()
            if name.startswith("discoverySection")
        } == expected


@pytest.mark.asyncio
async def test_mission_page_shows_discovery_progress_in_place():
    """The progress of a discovery is shown in place on the survey mission page, along
    with a refreshed record listing, without a notification.
    """
    mission_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_discovery_detail_page,
        _build_discovery_message(
            mission_id, constants.DiscoveryStage.PROGRESS, details="3 files"
        ),
        subscribers.HandlerContext(
            resource_id=str(mission_id), resource_type=constants.ResourceType.MISSION
        ),
    )

    assert len(events) == 1
    assert "discoveryProgress" in events[0] and "3 files" in events[0]
    assert "listingVersion" in events[0]
    assert _SAME_PAGE_NOTIFICATION not in events[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modification, own_request, expected_notifications",
    [
        pytest.param(constants.DiscoveryStage.ENDED, False, 1, id="ended"),
        pytest.param(
            constants.DiscoveryStage.CANCELLED, True, 1, id="cancel failed, own"
        ),
        pytest.param(
            constants.DiscoveryStage.CANCELLED, False, 0, id="cancel failed, other"
        ),
    ],
)
async def test_mission_page_discovery_failure_notifications(
    modification, own_request, expected_notifications
):
    """A failed discovery is always notified on the survey mission page, while a failed
    cancellation of a discovery is notified only on the page of the user who requested
    it.
    """
    mission_id = uuid.uuid4()
    request_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_discovery_detail_page,
        _build_discovery_message(
            mission_id,
            modification,
            succeeded=False,
            details="reason",
            request_id=request_id if own_request else None,
        ),
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            request_id=request_id,
        ),
    )

    assert (
        sum(_SAME_PAGE_NOTIFICATION in event for event in events)
        == expected_notifications
    )


def _build_derivation_message(record_id, mission_id, stage, succeeded=True):
    return message_schemas.DerivationMessage(
        request_id=uuid.uuid4(),
        resource_type=constants.ResourceType.RECORD,
        resource_id=str(record_id),
        parent_resource_id=str(mission_id),
        stage=stage,
        succeeded=succeeded,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_type, own_item, stage, succeeded, expected",
    [
        pytest.param(
            constants.ResourceType.MISSION,
            False,
            constants.DerivationStage.ENDED,
            True,
            None,
            id="other mission",
        ),
        pytest.param(
            constants.ResourceType.RECORD,
            True,
            constants.DerivationStage.ENDED,
            True,
            "/detail",
            id="record",
        ),
        # a reload would close the page's stream, which could then miss the end
        pytest.param(
            constants.ResourceType.RECORD,
            True,
            constants.DerivationStage.STARTED,
            True,
            None,
            id="record, started",
        ),
        pytest.param(
            constants.ResourceType.RECORD,
            True,
            constants.DerivationStage.PROGRESS,
            True,
            None,
            id="record, in progress",
        ),
        pytest.param(
            constants.ResourceType.RECORD,
            True,
            constants.DerivationStage.ENDED,
            False,
            None,
            id="record, nothing stored",
        ),
        pytest.param(
            constants.ResourceType.RECORD,
            False,
            constants.DerivationStage.ENDED,
            True,
            None,
            id="other record",
        ),
    ],
)
async def test_detail_pages_refresh_on_derivation(
    resource_type, own_item, stage, succeeded, expected
):
    """A record page is reloaded once the previews of its record have been generated and
    stored, but not while their generation starts or progresses, nor when nothing was
    stored, nor for other records. A survey mission page does not react to the previews
    of records of other survey missions.
    """
    record_id = uuid.uuid4()
    mission_id = uuid.uuid4()
    context_resource_id = (
        record_id if resource_type == constants.ResourceType.RECORD else mission_id
    )

    events = await _collect(
        common_handlers.handle_derivation_detail_page,
        _build_derivation_message(record_id, mission_id, stage, succeeded),
        subscribers.HandlerContext(
            resource_id=str(context_resource_id if own_item else uuid.uuid4()),
            resource_type=resource_type,
            url_resolver=lambda name, **params: f"/{name.split(':')[1]}",
        ),
    )

    if expected is None:
        assert events == []
    else:
        assert len(events) == 1 and expected in events[0]
        assert _SAME_PAGE_NOTIFICATION not in events[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage, succeeded, expected_deriving, refreshes_list_page",
    [
        pytest.param(
            constants.DerivationStage.STARTED, True, True, False, id="started"
        ),
        pytest.param(
            constants.DerivationStage.PROGRESS, True, True, False, id="in progress"
        ),
        pytest.param(constants.DerivationStage.ENDED, True, False, True, id="stored"),
        pytest.param(
            constants.DerivationStage.ENDED, False, False, False, id="nothing stored"
        ),
    ],
)
async def test_record_listings_show_which_records_are_being_derived(
    stage, succeeded, expected_deriving, refreshes_list_page
):
    """While the previews of a record are being generated, the survey mission page and
    the record list page mark the record as busy, and remove the mark when generation
    ends. The record list page is refreshed once the previews are stored, and the survey
    mission page refreshes its record listing at every stage.
    """
    record_id = uuid.uuid4()
    mission_id = uuid.uuid4()
    message = _build_derivation_message(record_id, mission_id, stage, succeeded)

    (mission_page_event,) = await _collect(
        common_handlers.handle_derivation_detail_page,
        message,
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            user=_USER,
        ),
    )
    (list_page_event,) = await _collect(
        common_handlers.handle_derivation_list_page,
        message,
        subscribers.HandlerContext(user=_USER),
    )

    mission_page_signals = _parse_patched_signals(mission_page_event)
    list_page_signals = _parse_patched_signals(list_page_event)
    # false rather than removed, which would leave the spinner shown
    assert mission_page_signals["_derivingIds"] == {str(record_id): expected_deriving}
    assert list_page_signals["_derivingIds"] == {str(record_id): expected_deriving}
    # at every stage, as a patch without it could make the page's throttle drop the
    # re-fetch an earlier message asked for
    assert "listingVersion" in mission_page_signals
    assert list_page_signals.get("derivedRecordId") == (
        str(record_id) if refreshes_list_page else None
    )


@pytest.mark.asyncio
async def test_record_listings_send_no_record_ids_to_anonymous_visitors():
    """Anonymous visitors receive no record identifiers during preview generation: the
    survey mission page only refreshes its record listing, and the record list page
    receives nothing.
    """
    record_id = uuid.uuid4()
    mission_id = uuid.uuid4()
    mission_page = subscribers.HandlerContext(
        resource_id=str(mission_id), resource_type=constants.ResourceType.MISSION
    )
    started = _build_derivation_message(
        record_id, mission_id, constants.DerivationStage.STARTED
    )
    ended = _build_derivation_message(
        record_id, mission_id, constants.DerivationStage.ENDED
    )

    for message in (started, ended):
        (event,) = await _collect(
            common_handlers.handle_derivation_detail_page, message, mission_page
        )
        # the mission page still re-fetches its records
        assert list(_parse_patched_signals(event)) == ["listingVersion"]
    assert not await _collect(
        common_handlers.handle_derivation_list_page, ended, subscribers.HandlerContext()
    )


def _create_jinja_environment(settings) -> jinja2.Environment:
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(settings.templates_dir), autoescape=True
    )
    configure_jinja_env(environment)
    environment.globals["icons"] = settings.icons.model_dump()
    return environment


def _resolve_url(name: str, **params) -> str:
    return "/".join((f"/{name}", *(str(value) for value in params.values())))


def _build_thumbnail_message(
    resource_type, resource_id, parent_resource_id=None, stage=None, succeeded=True
):
    return message_schemas.DerivationMessage(
        request_id=uuid.uuid4(),
        resource_type=resource_type,
        resource_id=str(resource_id),
        parent_resource_id=(
            str(parent_resource_id) if parent_resource_id is not None else None
        ),
        stage=stage or constants.DerivationStage.ENDED,
        succeeded=succeeded,
    )


async def _store_thumbnails(db_session_maker, survey_mission) -> None:
    """Store thumbnails for a survey mission and for its project."""
    async with db_session_maker() as session:
        await project_commands.set_project_thumbnail(
            session,
            identifiers.ProjectId(survey_mission.project_id),
            b"project thumbnail",
        )
        await mission_commands.set_survey_mission_thumbnail(
            session,
            identifiers.SurveyMissionId(survey_mission.id),
            b"survey mission thumbnail",
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_type",
    [
        pytest.param(constants.ResourceType.PROJECT, id="project"),
        pytest.param(constants.ResourceType.MISSION, id="survey mission"),
    ],
)
async def test_listings_show_stored_thumbnails_in_place(
    settings, db_session_maker, sample_survey_missions, admin_user, resource_type
):
    """Once the thumbnail of a project or survey mission is stored, the listings showing
    it display the thumbnail in place of its placeholder, without being reloaded and
    without showing a notification.
    """
    survey_mission = sample_survey_missions[0]
    project_id = survey_mission.project_id
    await _store_thumbnails(db_session_maker, survey_mission)
    if resource_type == constants.ResourceType.PROJECT:
        message = _build_thumbnail_message(resource_type, project_id)
        element_id = f"project-thumbnail-{project_id}"
        thumbnail_url = f"/projects:get_thumbnail/{project_id}?v="
    else:
        message = _build_thumbnail_message(resource_type, survey_mission.id, project_id)
        element_id = f"survey-mission-thumbnail-{survey_mission.id}"
        thumbnail_url = f"/survey_missions:get_thumbnail/{survey_mission.id}?v="

    events = await _collect(
        common_handlers.handle_thumbnail_derivation,
        message,
        subscribers.HandlerContext(
            resource_type=resource_type,
            target_page=constants.PageType.RESOURCE_LIST,
            user=admin_user,
            db_session_factory=db_session_maker,
            jinja_environment=_create_jinja_environment(settings),
            url_resolver=_resolve_url,
        ),
    )

    (event,) = events
    assert "datastar-patch-elements" in event
    assert f'id="{element_id}"' in event
    assert thumbnail_url in event
    assert _SAME_PAGE_NOTIFICATION not in event
    assert _STORED_NOTIFICATION not in event


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_type, own_resource, expected",
    [
        pytest.param(
            constants.ResourceType.MISSION, True, True, id="own survey mission"
        ),
        pytest.param(
            constants.ResourceType.MISSION,
            False,
            False,
            id="survey mission of another project",
        ),
        # the project's page does not show its own thumbnail
        pytest.param(constants.ResourceType.PROJECT, True, False, id="the project"),
    ],
)
async def test_project_page_shows_thumbnails_of_its_survey_missions(
    settings,
    db_session_maker,
    sample_survey_missions,
    admin_user,
    resource_type,
    own_resource,
    expected,
):
    """A project's page displays the stored thumbnails of its own survey missions in its
    listing, but receives neither those of the survey missions of other projects nor its
    own, which it does not show.
    """
    survey_mission = sample_survey_missions[0]
    project_id = survey_mission.project_id
    await _store_thumbnails(db_session_maker, survey_mission)
    message = (
        _build_thumbnail_message(resource_type, survey_mission.id, project_id)
        if resource_type == constants.ResourceType.MISSION
        else _build_thumbnail_message(resource_type, project_id)
    )

    events = await _collect(
        common_handlers.handle_thumbnail_derivation,
        message,
        subscribers.HandlerContext(
            resource_id=str(project_id if own_resource else uuid.uuid4()),
            resource_type=constants.ResourceType.PROJECT,
            target_page=constants.PageType.RESOURCE_DETAIL,
            user=admin_user,
            db_session_factory=db_session_maker,
            jinja_environment=_create_jinja_environment(settings),
            url_resolver=_resolve_url,
        ),
    )

    if expected:
        (event,) = events
        assert f'id="survey-mission-thumbnail-{survey_mission.id}"' in event
    else:
        assert events == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_listings_send_no_draft_thumbnails_to_anonymous_visitors(
    settings, db_session_maker, sample_projects, sample_survey_missions
):
    """Anonymous visitors, who only see published projects and survey missions, receive
    nothing when the thumbnail of a draft project or survey mission is stored.
    """
    survey_mission = sample_survey_missions[0]
    assert survey_mission.status == constants.SurveyMissionStatus.DRAFT
    (project,) = [p for p in sample_projects if p.id == survey_mission.project_id]
    assert project.status == constants.ProjectStatus.DRAFT
    await _store_thumbnails(db_session_maker, survey_mission)
    context = subscribers.HandlerContext(
        target_page=constants.PageType.RESOURCE_LIST,
        db_session_factory=db_session_maker,
        jinja_environment=_create_jinja_environment(settings),
        url_resolver=_resolve_url,
    )

    for message in (
        _build_thumbnail_message(
            constants.ResourceType.PROJECT, survey_mission.project_id
        ),
        _build_thumbnail_message(
            constants.ResourceType.MISSION,
            survey_mission.id,
            survey_mission.project_id,
        ),
    ):
        assert (
            await _collect(
                common_handlers.handle_thumbnail_derivation, message, context
            )
            == []
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage, succeeded",
    [
        pytest.param(constants.DerivationStage.STARTED, True, id="started"),
        pytest.param(constants.DerivationStage.PROGRESS, True, id="in progress"),
        pytest.param(constants.DerivationStage.ENDED, False, id="nothing stored"),
    ],
)
async def test_listings_ignore_thumbnails_not_stored(stage, succeeded):
    """Listings do not change while a thumbnail is being generated, nor when its
    generation stored nothing.
    """
    events = await _collect(
        common_handlers.handle_thumbnail_derivation,
        _build_thumbnail_message(
            constants.ResourceType.PROJECT,
            uuid.uuid4(),
            stage=stage,
            succeeded=succeeded,
        ),
        subscribers.HandlerContext(target_page=constants.PageType.RESOURCE_LIST),
    )

    assert events == []
