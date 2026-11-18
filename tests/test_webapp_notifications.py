"""Notifications on pages

Notifications about changes to catalog entries are written in the language of the user,
name the entry concerned, and present the reasons for failures clearly and safely.
"""

import json
import re
import uuid
from pathlib import Path

import pytest
from starlette_babel import (
    get_translator,
    switch_locale,
)

import seis_lab_data
from seis_lab_data import (
    constants,
    errors,
    subscribers,
)
from seis_lab_data.schemas import messages as message_schemas
from seis_lab_data.webapp.streamhandlers import common as common_handlers


@pytest.fixture
def translations():
    """Load the compiled translation catalogs of the application."""
    # compiled into the image, as by `seis-lab-data translations compile`
    get_translator().load_from_directory(
        Path(seis_lab_data.__file__).parent / "translations"
    )


def _same_page_payload(event: str) -> dict:
    """Return the payload of the notification shown by an SSE event."""
    return json.loads(re.search(r"showFlash\((.*)\)</script>", event).group(1))


def _stored_payload(event: str) -> dict:
    """Return the payload of the notification stored for the next page."""
    stored = re.search(r"localStorage\.setItem\('sld:flash', (.*)\);</script>", event)
    return json.loads(json.loads(stored.group(1)))


def _deleted(resource_name, succeeded=True, request_id=None):
    return message_schemas.ResourceModificationMessage(
        request_id=request_id or uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(uuid.uuid4()),
        resource_name=resource_name,
        modification=constants.ResourceModification.DELETED,
        succeeded=succeeded,
        details=None if succeeded else "it is busy",
    )


async def _notify_on_list_page(message, request_id=None):
    events = [
        event
        async for event in common_handlers.handle_resource_modification_list_page(
            message, subscribers.HandlerContext(request_id=request_id)
        )
    ]
    return _same_page_payload(events[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "locale, expected_title, expected_message",
    [
        pytest.param("en", "Success — survey mission", "“m1” was deleted.", id="en"),
        pytest.param(
            "pt", "Sucesso — missão", "Eliminação de «m1» concluída.", id="pt"
        ),
    ],
)
async def test_notification_names_its_resource_in_the_current_locale(
    translations, locale, expected_title, expected_message
):
    """A notification of a deletion names the deleted entry and its kind in the language
    of the user, English or Portuguese, and disappears by itself.
    """
    with switch_locale(locale):
        payload = await _notify_on_list_page(_deleted("m1"))

    assert payload == {
        "title": expected_title,
        "message": expected_message,
        "category": "success",
        "autohide": True,
    }


@pytest.mark.asyncio
async def test_error_notification_stays_until_dismissed(translations):
    """A notification of a failed deletion is shown as an error, includes the reason for
    the failure, and stays on the page until the user dismisses it.
    """
    request_id = uuid.uuid4()

    with switch_locale("en"):
        payload = await _notify_on_list_page(
            _deleted("m1", succeeded=False, request_id=request_id), request_id
        )

    assert payload["title"] == "Error — survey mission"
    assert payload["message"] == "Could not delete “m1”: it is busy"
    assert payload["category"] == "danger"
    assert payload["autohide"] is False


@pytest.mark.asyncio
async def test_notification_falls_back_to_the_resource_id(translations):
    """When an entry has no name, notifications identify it by its identifier."""
    message = _deleted(None)

    with switch_locale("en"):
        payload = await _notify_on_list_page(message)

    assert payload["message"] == f"“{message.resource_id}” was deleted."


@pytest.mark.asyncio
async def test_status_change_notification_translates_the_status(translations):
    """A notification of a status change shows the new status in the language of the
    user.
    """
    record_id = str(uuid.uuid4())
    message = message_schemas.ResourceStatusChangedMessage(
        request_id=uuid.uuid4(),
        resource_type=constants.ResourceType.RECORD,
        resource_id=record_id,
        resource_name="r1",
        succeeded=True,
        new_status=constants.SurveyRelatedRecordStatus.PUBLISHED.value,
    )

    with switch_locale("pt"):
        events = [
            event
            async for event in common_handlers.handle_resource_status_changed_detail_page(
                message,
                subscribers.HandlerContext(
                    resource_id=record_id,
                    resource_type=constants.ResourceType.RECORD,
                ),
            )
        ]

    payload = _same_page_payload(events[0])
    assert payload["title"] == "Informação — registo"
    assert payload["message"] == "O estado de «r1» passou a público."


@pytest.mark.asyncio
async def test_names_cannot_break_out_of_the_notification_script(translations):
    """Entry names containing web page markup are shown as plain text in notifications
    and cannot insert content into the page, both in notifications shown immediately and
    in those kept for the next page.
    """
    name = "</script><img src=x onerror=alert(1)>"
    message = _deleted(name)

    with switch_locale("en"):
        same_page_events = [
            event
            async for event in common_handlers.handle_resource_modification_list_page(
                message, subscribers.HandlerContext()
            )
        ]
        stored_events = [
            event
            async for event in common_handlers.handle_resource_modification_edit_page(
                message,
                subscribers.HandlerContext(
                    resource_id=message.resource_id,
                    url_resolver=lambda name, **params: f"/{name}",
                ),
            )
        ]

    for event, get_payload in (
        (same_page_events[0], _same_page_payload),
        (stored_events[0], _stored_payload),
    ):
        # only the script's own closing tag, and no other markup
        assert event.count("</script>") == 1
        assert "<img" not in event
        # the name is still shown as it is, by the page, as text
        assert get_payload(event)["message"] == f"“{name}” was deleted."


def _failed_update(details, details_params):
    return message_schemas.ResourceModificationMessage(
        request_id=uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(uuid.uuid4()),
        resource_name="m1",
        modification=constants.ResourceModification.UPDATED,
        succeeded=False,
        details=details,
        details_params=details_params,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "locale, expected_message",
    [
        pytest.param(
            "en",
            "Could not update “m1”: Cannot update the survey mission because its "
            "status is under discovery.",
            id="en",
        ),
        pytest.param(
            "pt",
            "Não foi possível atualizar «m1»: Não é possível atualizar a missão "
            "porque o seu estado é em descoberta.",
            id="pt",
        ),
    ],
)
async def test_failure_details_are_translated_along_with_their_status(
    translations, locale, expected_message
):
    """The reason given for a failed update is shown in the language of the user,
    including the status it mentions.
    """
    message = _failed_update(
        errors.N_("Cannot update the survey mission because its status is %(status)s."),
        {"status": constants.SurveyMissionStatus.UNDER_DISCOVERY.value},
    )

    with switch_locale(locale):
        payload = await _notify_on_list_page(message, request_id=message.request_id)

    assert payload["message"] == expected_message


@pytest.mark.asyncio
async def test_failure_details_keep_their_values_untranslated(translations):
    """Values inserted into the reason for a failure, such as an identifier, are shown
    as they are, even when they coincide with a word that has a translation.
    """
    message = _failed_update(
        errors.N_("Survey mission %(id)s does not exist."), {"id": "draft"}
    )

    with switch_locale("pt"):
        payload = await _notify_on_list_page(message, request_id=message.request_id)

    assert payload["message"] == (
        "Não foi possível atualizar «m1»: A missão draft não existe."
    )


@pytest.mark.asyncio
async def test_failure_details_missing_from_the_catalogs_are_shown_as_they_are(
    translations,
):
    """A failure reason for which no translation exists is shown as it is."""
    message = _failed_update("connection refused (100% busy)", {})

    with switch_locale("pt"):
        payload = await _notify_on_list_page(message, request_id=message.request_id)

    assert payload["message"] == (
        "Não foi possível atualizar «m1»: connection refused (100% busy)"
    )
