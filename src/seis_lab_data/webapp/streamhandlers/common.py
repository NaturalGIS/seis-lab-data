import json
import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from datastar_py.sse import ServerSentEventGenerator
from datastar_py.starlette import DatastarEvent
from starlette_babel import gettext_lazy as _

from ... import (
    constants,
    subscribers,
)
from ...operations import (
    surveymissions as mission_ops,
    surveyrelatedrecords as record_ops,
)
from ...schemas import (
    identifiers,
    messages as message_schemas,
    webui as webui_schemas,
)

logger = logging.getLogger(__name__)

# The notification's header names the type of its resource, so these sentences
# leave it out - which also spares translations from agreeing with its gender.
# User data, such as names, is inserted into them untranslated.
_MODIFICATION_SUCCEEDED = {
    constants.ResourceModification.CREATED: _("“%(name)s” was created."),
    constants.ResourceModification.UPDATED: _("“%(name)s” was updated."),
    constants.ResourceModification.DELETED: _("“%(name)s” was deleted."),
}
_MODIFICATION_FAILED = {
    constants.ResourceModification.CREATED: _(
        "Could not create “%(name)s”: %(details)s"
    ),
    constants.ResourceModification.UPDATED: _(
        "Could not update “%(name)s”: %(details)s"
    ),
    constants.ResourceModification.DELETED: _(
        "Could not delete “%(name)s”: %(details)s"
    ),
}
_STATUS_ENUMS = {
    constants.ResourceType.PROJECT: constants.ProjectStatus,
    constants.ResourceType.MISSION: constants.SurveyMissionStatus,
    constants.ResourceType.RECORD: constants.SurveyRelatedRecordStatus,
}
_CATEGORY_LABELS = {
    "info": _("info"),
    "success": _("success"),
    "error": _("error"),
}


def _get_flash_payload(notification: webui_schemas.Notification) -> dict[str, Any]:
    """Return what the page's `showFlash` needs, translated to the current locale."""
    title = str(_CATEGORY_LABELS[notification.category])
    if notification.resource_type is not None:
        title += f" — {notification.resource_type.get_translated_value()}"
    return {
        "title": title[:1].upper() + title[1:],
        "message": notification.message,
        "category": {
            "success": "success",
            "error": "danger",
        }.get(notification.category, "info"),
        # errors stay until dismissed, as their details may take a while to read
        "autohide": notification.category != "error",
    }


def _get_modification_notification(
    message: message_schemas.ResourceModificationMessage,
) -> webui_schemas.Notification:
    """Return the notification of a resource modification's outcome."""
    variables = {
        "name": message.resource_name or message.resource_id,
        "details": message.details,
    }
    if message.succeeded:
        return webui_schemas.Notification(
            message=_MODIFICATION_SUCCEEDED[message.modification] % variables,
            category="success",
            resource_type=message.resource_type,
        )
    return webui_schemas.Notification(
        message=_MODIFICATION_FAILED[message.modification] % variables,
        category="error",
        resource_type=message.resource_type,
    )


def _get_status_changed_notification(
    message: message_schemas.ResourceStatusChangedMessage,
) -> webui_schemas.Notification:
    """Return the notification of a resource status change's outcome."""
    name = message.resource_name or message.resource_id
    if not message.succeeded:
        return webui_schemas.Notification(
            message=_("Could not change the status of “%(name)s”: %(details)s")
            % {"name": name, "details": message.details},
            category="error",
            resource_type=message.resource_type,
        )
    status_enum = _STATUS_ENUMS.get(message.resource_type)
    return webui_schemas.Notification(
        message=_("“%(name)s” changed status to %(status)s.")
        % {
            "name": name,
            "status": (
                status_enum(message.new_status).get_translated_value()
                if status_enum is not None
                else message.new_status
            ),
        },
        resource_type=message.resource_type,
    )


def _to_script_literal(value: Any) -> str:
    """Serialize a value as a JavaScript literal that is safe inside a script tag.

    Scripts are sent as HTML, where a `</script>` within a string, such as a
    resource name, would end the script early and have the rest parsed as HTML.
    """
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


async def flash_ui_message_after_redirect(
    notification: webui_schemas.Notification,
) -> AsyncGenerator[DatastarEvent, None]:
    payload = _get_flash_payload(notification)
    logger.debug(f"{payload=}")
    yield ServerSentEventGenerator.execute_script(
        f"localStorage.setItem('sld:flash', {_to_script_literal(json.dumps(payload))});"
    )


async def flash_ui_message_same_page(
    notification: webui_schemas.Notification,
) -> AsyncGenerator[DatastarEvent, None]:
    payload = _get_flash_payload(notification)
    yield ServerSentEventGenerator.execute_script(
        f"showFlash({_to_script_literal(payload)})"
    )


async def handle_resource_modification_new_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    # this page only cares about the message that corresponds to its own creation request
    if context.request_id != message.request_id:
        return

    # these resource types have no detail page of their own, so - unlike the
    # others handled below - we always send the user back to their listing
    # page, regardless of whether creation succeeded, and report the outcome
    # via a flash notification
    list_page_route_name = {
        constants.ResourceType.ASSET_DISCOVERY_CONFIG: "asset_discovery_configurations:list",
        constants.ResourceType.CATEGORY: "dataset_categories:list",
        constants.ResourceType.WORKFLOW_STAGE: "workflow_stages:list",
    }.get(message.resource_type)

    if list_page_route_name is not None:
        async for event in flash_ui_message_after_redirect(
            _get_modification_notification(message)
        ):
            yield event
        yield ServerSentEventGenerator.redirect(
            str(context.url_resolver(list_page_route_name))
        )
        return

    if not message.succeeded:
        yield ServerSentEventGenerator.patch_signals({"submitting": False})
        async for event in flash_ui_message_same_page(
            _get_modification_notification(message)
        ):
            yield event
        return

    async for event in flash_ui_message_after_redirect(
        _get_modification_notification(message)
    ):
        yield event

    match message.resource_type:
        case constants.ResourceType.PROJECT:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "projects:detail", project_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.MISSION:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_missions:detail", survey_mission_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.RECORD:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_related_records:detail",
                        survey_related_record_id=message.resource_id,
                    )
                )
            )


async def handle_resource_modification_list_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if (
        not message.succeeded
    ):  # only send notification if the context has the same request_id
        if context.request_id == message.request_id:
            async for event in flash_ui_message_same_page(
                _get_modification_notification(message)
            ):
                yield event
    else:
        async for event in flash_ui_message_same_page(
            _get_modification_notification(message)
        ):
            yield event
    # update datastar signal that frontend recognizes as needing to re-fetch listing
    yield ServerSentEventGenerator.patch_signals(
        {"listingVersion": int(time.time() * 1000)}
    )


async def handle_resource_status_changed_list_page(
    message: message_schemas.ResourceStatusChangedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Re-fetch a listing as one of its items changes status."""
    if message.succeeded:
        yield ServerSentEventGenerator.patch_signals(
            {"listingVersion": int(time.time() * 1000)}
        )


async def handle_bulk_resource_modification(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Flash the outcome of a bulk update and return to the mission detail page.

    There's no single `resource_id` to match on for a bulk action, so this
    matches on `request_id` instead - `context.resource_id` is repurposed to
    carry the survey mission to redirect back to.
    """
    if message.request_id != context.request_id:
        return

    if message.succeeded:
        notification = webui_schemas.Notification(
            message=_("Bulk update succeeded. Updated: %(count)s.")
            % {"count": message.affected_count},
            category="success",
            resource_type=message.resource_type,
        )
    else:
        notification = webui_schemas.Notification(
            message=_("Bulk update failed: %(details)s") % {"details": message.details},
            category="error",
            resource_type=message.resource_type,
        )
    async for event in flash_ui_message_after_redirect(notification):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "survey_missions:detail", survey_mission_id=context.resource_id
            )
        )
    )


async def handle_resource_modification_edit_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Enqueue validation and redirect to project detail page after editing."""
    logger.debug(f"{message=}")
    logger.debug(f"{context=}")
    if message.resource_id != context.resource_id:
        return

    async for event in flash_ui_message_after_redirect(
        _get_modification_notification(message)
    ):
        yield event

    match message.resource_type:
        case constants.ResourceType.PROJECT:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "projects:detail", project_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.MISSION:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_missions:detail", survey_mission_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.RECORD:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_related_records:detail",
                        survey_related_record_id=message.resource_id,
                    )
                )
            )
        case constants.ResourceType.ASSET_DISCOVERY_CONFIG:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("asset_discovery_configurations:list"))
            )
        case constants.ResourceType.CATEGORY:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("dataset_categories:list"))
            )
        case constants.ResourceType.WORKFLOW_STAGE:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("workflow_stages:list"))
            )


async def _handle_project_modification_detail_page(
    message: message_schemas.ResourceModificationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    project_id = identifiers.ProjectId(uuid.UUID(context.resource_id))
    if message.resource_type == constants.ResourceType.PROJECT:
        # are we handling this project's details?
        if message.resource_id != context.resource_id:
            return

        if not message.succeeded:  # if same request_id, show a notification
            if message.request_id == context.request_id:
                async for event in flash_ui_message_same_page(
                    _get_modification_notification(message)
                ):
                    yield event

        else:
            match message.modification:
                case constants.ResourceModification.UPDATED:
                    logger.debug(
                        f"Project {message.resource_id!r} has been updated - re-rendering its details..."
                    )
                    async for event in flash_ui_message_after_redirect(
                        _get_modification_notification(message)
                    ):
                        yield event
                    yield ServerSentEventGenerator.redirect(
                        str(
                            context.url_resolver(
                                "projects:detail", project_id=project_id
                            )
                        )
                    )
                case constants.ResourceModification.DELETED:
                    async for event in flash_ui_message_after_redirect(
                        _get_modification_notification(message)
                    ):
                        yield event
                    yield ServerSentEventGenerator.redirect(
                        str(context.url_resolver("projects:list"))
                    )
                case _:
                    logger.debug(
                        f"Don't know how to handle modification {message.modification!r}, skipping..."
                    )

    elif message.resource_type == constants.ResourceType.MISSION and message.succeeded:
        # only care about survey_mission if it is child of project in context
        survey_mission_id = identifiers.SurveyMissionId(uuid.UUID(message.resource_id))
        if message.parent_resource_id is not None:
            # a deleted mission is no longer in the DB, but the message carries its parent
            if message.parent_resource_id != context.resource_id:
                logger.debug(
                    f"survey_mission {survey_mission_id!r} is not child of current project - skipping..."
                )
                return
        else:
            async with context.db_session_factory() as session:
                if (
                    db_mission := await mission_ops.get_survey_mission(
                        survey_mission_id, context.user, session
                    )
                ) is None:
                    logger.debug(
                        f"Could not find survey_mission with id {message.resource_id!r} in the DB"
                    )
                    return
                if identifiers.ProjectId(db_mission.project_id) != project_id:
                    logger.debug(
                        f"survey_mission {survey_mission_id!r} is not child of current project - skipping..."
                    )
                    return
        logger.debug(
            f"Survey mission {message.resource_id!r} is a child of the current project - asking frontend to re-fetch mission listing..."
        )
        async for event in flash_ui_message_same_page(
            _get_modification_notification(message)
        ):
            yield event
        # update datastar signal which frontend uses to check when needing to re-fetch list of project child missions
        yield ServerSentEventGenerator.patch_signals(
            {"listingVersion": int(time.time() * 1000)}
        )

    elif message.resource_type == constants.ResourceType.RECORD and message.succeeded:
        # only care about record if it is grandchild of project in context
        record_id = identifiers.SurveyRelatedRecordId(uuid.UUID(message.resource_id))
        async with context.db_session_factory() as session:
            if (
                record_info := await record_ops.get_survey_related_record(
                    record_id, context.user, session
                )
            ) is None:
                logger.debug(
                    f"Could not find survey_related_record with id {message.resource_id!r} in the DB"
                )
                return
            db_record = record_info[0]
            if identifiers.ProjectId(db_record.survey_mission.project_id) != project_id:
                logger.debug(
                    f"survey_related_record {record_id!r} is not grandchild of current project - skipping..."
                )
                return
        logger.debug(
            f"Survey-related record {message.resource_id!r} is grandchild of current project - asking frontend to re-fetch mission listing..."
        )
        async for event in flash_ui_message_same_page(
            _get_modification_notification(message)
        ):
            yield event
        # update datastar signal which frontend uses to check when needing to re-fetch list of project child missions
        yield ServerSentEventGenerator.patch_signals(
            {"listingVersion": int(time.time() * 1000)}
        )


async def _handle_survey_mission_modification_detail_page(
    message: message_schemas.ResourceModificationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    mission_id = identifiers.SurveyMissionId(uuid.UUID(context.resource_id))
    if message.resource_type == constants.ResourceType.MISSION:
        # are we handling this mission's details?
        if message.resource_id != context.resource_id:
            return

        if not message.succeeded:  # if same request_id, show a notification
            if message.request_id == context.request_id:
                async for event in flash_ui_message_same_page(
                    _get_modification_notification(message)
                ):
                    yield event

        else:
            match message.modification:
                case constants.ResourceModification.UPDATED:
                    logger.debug(
                        f"Survey mission {message.resource_id!r} has been updated - re-rendering its details..."
                    )
                    # TODO: yield re-render of mission details
                case constants.ResourceModification.DELETED:
                    async for event in flash_ui_message_after_redirect(
                        _get_modification_notification(message)
                    ):
                        yield event
                    if (project_id := message.parent_resource_id) is not None:
                        redirect_to = context.url_resolver(
                            "projects:detail", project_id=project_id
                        )
                    else:
                        redirect_to = context.url_resolver("survey_missions:list")

                    yield ServerSentEventGenerator.redirect(str(redirect_to))
                case _:
                    logger.debug(
                        f"Don't know how to handle modification {message.modification!r}, skipping..."
                    )

    elif message.resource_type == constants.ResourceType.RECORD and message.succeeded:
        # only care about record if it is child of mission in context
        record_id = identifiers.SurveyRelatedRecordId(uuid.UUID(message.resource_id))
        if message.parent_resource_id is not None:
            # a deleted record is no longer in the DB, but the message carries its parent
            if message.parent_resource_id != context.resource_id:
                logger.debug(
                    f"survey_related_record {record_id!r} is not child of current mission - skipping..."
                )
                return
        else:
            async with context.db_session_factory() as session:
                if (
                    record_info := await record_ops.get_survey_related_record(
                        record_id, context.user, session
                    )
                ) is None:
                    logger.debug(
                        f"Could not find survey_related_record with id {message.resource_id!r} in the DB"
                    )
                    return
                db_record = record_info[0]
                if (
                    identifiers.SurveyMissionId(db_record.survey_mission_id)
                    != mission_id
                ):
                    logger.debug(
                        f"survey_related_record {record_id!r} is not child of current mission - skipping..."
                    )
                    return
        logger.debug(
            f"Survey-related record {message.resource_id!r} is a child of the current mission - asking frontend to re-fetch record listing..."
        )
        # update datastar signal which frontend uses to check when needing to re-fetch list of mission child records
        yield ServerSentEventGenerator.patch_signals(
            {"listingVersion": int(time.time() * 1000)}
        )


async def _handle_survey_related_record_modification_detail_page(
    message: message_schemas.ResourceModificationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.resource_id != context.resource_id:
        # are we handling this record's details?
        return

    if not message.succeeded:  # if same request_id, show a notification
        if message.request_id == context.request_id:
            async for event in flash_ui_message_same_page(
                _get_modification_notification(message)
            ):
                yield event
    else:
        match message.modification:
            case constants.ResourceModification.UPDATED:
                logger.debug(
                    f"Survey-related record {message.resource_id!r} has been updated - re-rendering its details..."
                )
                yield ServerSentEventGenerator.redirect(
                    str(
                        context.url_resolver(
                            "survey_related_records:detail",
                            survey_related_record_id=message.resource_id,
                        )
                    )
                )
            case constants.ResourceModification.DELETED:
                async for event in flash_ui_message_after_redirect(
                    _get_modification_notification(message)
                ):
                    yield event
                if (mission_id := message.parent_resource_id) is not None:
                    redirect_to = context.url_resolver(
                        "survey_missions:detail", survey_mission_id=mission_id
                    )
                else:
                    redirect_to = context.url_resolver("survey_related_records:list")

                yield ServerSentEventGenerator.redirect(str(redirect_to))
            case _:
                logger.debug(
                    f"Don't know how to handle modification {message.modification!r}, skipping..."
                )


async def handle_resource_status_changed_detail_page(
    message: message_schemas.ResourceStatusChangedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Handle status changes for an item's detail page."""
    match context.resource_type:
        case constants.ResourceType.PROJECT:
            async for event in _handle_project_status_changed_detail_page(
                message, context, done
            ):
                yield event
        case constants.ResourceType.MISSION:
            async for event in _handle_survey_mission_status_changed_detail_page(
                message, context, done
            ):
                yield event
        case _:
            if (
                message.succeeded
                and message.resource_type == constants.ResourceType.MISSION
                and message.resource_id == context.parent_resource_id
            ):
                # the record's actions depend on whether its mission is under discovery
                yield ServerSentEventGenerator.patch_signals(
                    {"detailsVersion": int(time.time() * 1000)}
                )
                return
            if context.resource_id != message.resource_id:
                return
            match message.resource_type:
                case constants.ResourceType.RECORD:
                    # re-fetching the record's details rather than reloading the
                    # page, as for the busy statuses which come and go during
                    # tasks such as exports, reloading makes the page jumpy
                    async for event in flash_ui_message_same_page(
                        _get_status_changed_notification(message)
                    ):
                        yield event
                    if message.succeeded:
                        yield ServerSentEventGenerator.patch_signals(
                            {"detailsVersion": int(time.time() * 1000)}
                        )
                case _:
                    logger.debug(
                        f"Don't know how to handle a status change for {message!r}"
                    )


async def _handle_survey_mission_status_changed_detail_page(
    message: message_schemas.ResourceStatusChangedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Handle a status changed message in the context of a survey mission detail page.

    A status change of the page's mission is notified, and the mission's details
    and list of records are re-fetched in place. The page is not reloaded, as that
    would close its stream and lose the messages published until it reopens. A
    status change of a record of the mission re-fetches the list of records.
    """

    match message:
        case message_schemas.ResourceStatusChangedMessage(
            succeeded=True, resource_type=constants.ResourceType.MISSION
        ):
            if message.resource_id == context.resource_id:
                async for event in flash_ui_message_same_page(
                    _get_status_changed_notification(message)
                ):
                    yield event
                refresh_version = int(time.time() * 1000)
                signals = {
                    "status": message.new_status,
                    "detailsVersion": refresh_version,
                    "listingVersion": refresh_version,
                }
                if message.new_status == constants.SurveyMissionStatus.UNDER_DISCOVERY:
                    # the last progress of a previous discovery
                    signals["discoveryProgress"] = str(
                        _("discovery is running")
                    ).capitalize()
                yield ServerSentEventGenerator.patch_signals(signals)
        case message_schemas.ResourceStatusChangedMessage(
            succeeded=True,
            resource_type=constants.ResourceType.RECORD,
        ):
            record_id = identifiers.SurveyRelatedRecordId(
                uuid.UUID(message.resource_id)
            )
            # only care if record is a child of context's mission
            async with context.db_session_factory() as session:
                if (
                    record_info := await record_ops.get_survey_related_record(
                        survey_related_record_id=record_id,
                        initiator=context.user,
                        session=session,
                    )
                ) is not None and str(
                    record_info[0].survey_mission_id
                ) == context.resource_id:
                    # update datastar signal which frontend uses to check when needing to re-fetch list of project child missions
                    yield ServerSentEventGenerator.patch_signals(
                        {"listingVersion": int(time.time() * 1000)}
                    )


async def _handle_project_status_changed_detail_page(
    message: message_schemas.ResourceStatusChangedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Handle a status changed message in the context of a project detail page.

    If a project status changes and the user is looking at the project's detail page we want to refresh the page

    If a survey mission status changes and the user is looking at its parent project detail page we want to
    reload the list of survey missions because it may be modified

    If a survey-related record's status changes and the user is looking at its parent project detail page we want
    to reload the list of survey missions because it may be modified
    """

    match message:
        case message_schemas.ResourceStatusChangedMessage(
            succeeded=True, resource_type=constants.ResourceType.PROJECT
        ):
            if message.resource_id == context.resource_id:
                # stored for the page that the redirect below reloads
                async for event in flash_ui_message_after_redirect(
                    _get_status_changed_notification(message)
                ):
                    yield event
                yield ServerSentEventGenerator.redirect(
                    str(
                        context.url_resolver(
                            "projects:detail", project_id=message.resource_id
                        )
                    )
                )
        case message_schemas.ResourceStatusChangedMessage(
            succeeded=True,
            resource_type=constants.ResourceType.MISSION,
        ):
            mission_id = identifiers.SurveyMissionId(uuid.UUID(message.resource_id))
            # only care if mission is a child of context's project
            async with context.db_session_factory() as session:
                if (
                    db_mission := await mission_ops.get_survey_mission(
                        survey_mission_id=mission_id,
                        initiator=context.user,
                        session=session,
                    )
                ) is not None and str(db_mission.project_id) == context.resource_id:
                    async for event in flash_ui_message_same_page(
                        _get_status_changed_notification(message)
                    ):
                        yield event
                    # update datastar signal which frontend uses to check when needing to re-fetch list of project child missions
                    yield ServerSentEventGenerator.patch_signals(
                        {"listingVersion": int(time.time() * 1000)}
                    )
        case message_schemas.ResourceStatusChangedMessage(
            succeeded=True,
            resource_type=constants.ResourceType.RECORD,
        ):
            record_id = identifiers.SurveyRelatedRecordId(
                uuid.UUID(message.resource_id)
            )
            # only care if record's parent mission is child of the context's project
            async with context.db_session_factory() as session:
                if (
                    record_info := await record_ops.get_survey_related_record(
                        survey_related_record_id=record_id,
                        initiator=context.user,
                        session=session,
                    )
                ) is not None and str(
                    record_info[0].survey_mission.project_id
                ) == context.resource_id:
                    async for event in flash_ui_message_same_page(
                        _get_status_changed_notification(message)
                    ):
                        yield event
                    # update datastar signal which frontend uses to check when needing to re-fetch list of project child missions
                    yield ServerSentEventGenerator.patch_signals(
                        {"listingVersion": int(time.time() * 1000)}
                    )


async def handle_resource_modification_detail_page(
    message: message_schemas.ResourceModificationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    # resource might:
    # - have been updated - reload the resource details
    # - have been deleted - redirect to resource list page
    # - have had a child resource modified - only applies to SurveyMission and Project - ask the frontend to reload the list of child resources
    # - have been created - not relevant for the detail page
    # - have had its status changed - handled in another handler - need to update the status-related fields
    # - have had its discovery progressed - handled in another handler - only applies to SurveyMission: need to update the discovery-related fields
    logger.debug(f"{context=}")
    logger.debug(f"{message=}")

    match context.resource_type:
        case constants.ResourceType.PROJECT:
            async for event in _handle_project_modification_detail_page(
                message, context, done
            ):
                yield event
        case constants.ResourceType.MISSION:
            async for event in _handle_survey_mission_modification_detail_page(
                message, context, done
            ):
                yield event
        case constants.ResourceType.RECORD:
            async for event in _handle_survey_related_record_modification_detail_page(
                message, context, done
            ):
                yield event
        case _:
            if message.resource_id != context.resource_id:
                return
            if not message.succeeded:  # if same request_id, show a notification
                if message.request_id == context.request_id:
                    async for event in flash_ui_message_same_page(
                        _get_modification_notification(message)
                    ):
                        yield event
                return
            async for event in flash_ui_message_after_redirect(
                _get_modification_notification(message)
            ):
                yield event
            match message.resource_type:
                # regardless of it being an update or a delete, redirect to the listing page
                case constants.ResourceType.ASSET_DISCOVERY_CONFIG:
                    yield ServerSentEventGenerator.redirect(
                        str(context.url_resolver("asset_discovery_configurations:list"))
                    )
                case constants.ResourceType.CATEGORY:
                    yield ServerSentEventGenerator.redirect(
                        str(context.url_resolver("dataset_categories:list"))
                    )
                case constants.ResourceType.WORKFLOW_STAGE:
                    yield ServerSentEventGenerator.redirect(
                        str(context.url_resolver("workflow_stages:list"))
                    )


async def handle_discovery_detail_page(
    message: message_schemas.DiscoveryMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    # - have had its discovery progressed - only applies to SurveyMission: need to update the discovery-related fields
    logger.debug(f"{context=}")
    logger.debug(f"{message=}")
    if message.resource_id != context.resource_id:
        return
    variables = {
        "name": message.resource_name or message.resource_id,
        "details": message.details,
    }
    match message:
        case message_schemas.DiscoveryMessage(
            modification=constants.DiscoveryStage.PROGRESS
        ):
            # shown in place, along with the records found so far
            yield ServerSentEventGenerator.patch_signals(
                {
                    "discoveryProgress": message.details,
                    "listingVersion": int(time.time() * 1000),
                }
            )
            return
        case message_schemas.DiscoveryMessage(
            succeeded=False, modification=constants.DiscoveryStage.CANCELLED
        ):
            notification = webui_schemas.Notification(
                message=_("Could not cancel the discovery of “%(name)s”: %(details)s")
                % variables,
                category="error",
                resource_type=message.resource_type,
            )
        case message_schemas.DiscoveryMessage(succeeded=False):
            notification = webui_schemas.Notification(
                message=_("Discovery of “%(name)s” failed: %(details)s") % variables,
                category="error",
                resource_type=message.resource_type,
            )
        case message_schemas.DiscoveryMessage(
            modification=constants.DiscoveryStage.CANCELLED
        ):
            notification = webui_schemas.Notification(
                message=_("Discovery of “%(name)s” was cancelled: %(details)s")
                % variables,
                resource_type=message.resource_type,
            )
        case message_schemas.DiscoveryMessage(
            modification=constants.DiscoveryStage.ENDED
        ):
            notification = webui_schemas.Notification(
                message=_("Discovery of “%(name)s” ended: %(details)s") % variables,
                category="success",
                resource_type=message.resource_type,
            )
        case _:
            notification = webui_schemas.Notification(
                message=_("Discovery of “%(name)s” started.") % variables,
                resource_type=message.resource_type,
            )
    # failures are only shown to the page whose request failed, except for the
    # end of a running discovery, which concerns whoever is looking at the mission
    if (
        notification.category == "error"
        and message.request_id != context.request_id
        and message.modification != constants.DiscoveryStage.ENDED
    ):
        return
    async for event in flash_ui_message_same_page(notification):
        yield event


async def handle_derivation_detail_page(
    message: message_schemas.DerivationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Refresh a detail page as derived assets are stored for its item or its children.

    A record's detail page is reloaded. A mission's detail page re-fetches its list
    of records.
    """
    match context.resource_type:
        case constants.ResourceType.RECORD if (
            message.resource_id == context.resource_id
        ):
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_related_records:detail",
                        survey_related_record_id=message.resource_id,
                    )
                )
            )
        case constants.ResourceType.MISSION if (
            message.parent_resource_id == context.resource_id
        ):
            yield ServerSentEventGenerator.patch_signals(
                {"listingVersion": int(time.time() * 1000)}
            )


async def handle_export_detail_page(
    message: message_schemas.ExportMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Relay the progress and outcome of an item's export to its detail page.

    The export's start is not announced here, nor are the item's details
    re-fetched: both come with the item's status changes, into and out of
    being under export, which are handled on their own.
    """
    if message.resource_id != context.resource_id:
        return
    match message.stage:
        case constants.ExportStage.PROGRESS:
            # reported by the worker, which has no locale
            async for event in flash_ui_message_same_page(
                webui_schemas.Notification(
                    message=message.details, resource_type=message.resource_type
                )
            ):
                yield event
            return
        case constants.ExportStage.STARTED:
            return
        case _ if message.succeeded:
            notification = webui_schemas.Notification(
                message=_("“%(name)s” was exported to GeoNode: %(details)s")
                % {
                    "name": message.resource_name or message.resource_id,
                    "details": message.details,
                },
                category="success",
                resource_type=message.resource_type,
            )
        case _:
            notification = webui_schemas.Notification(
                message=_("Could not export “%(name)s” to GeoNode: %(details)s")
                % {
                    "name": message.resource_name or message.resource_id,
                    "details": message.details,
                },
                category="error",
                resource_type=message.resource_type,
            )
    async for event in flash_ui_message_same_page(notification):
        yield event
