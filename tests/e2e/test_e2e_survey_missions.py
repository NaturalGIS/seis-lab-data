import re
import uuid

import pytest
from playwright.sync_api import (
    expect,
    Page,
)


def _fill_project_form_minimal(page: Page, english_name: str):
    page.get_by_role("textbox", name="field-name-en").fill(english_name)


def _fill_survey_mission_form(page: Page, english_name: str):
    page.get_by_role("textbox", name="field-name-en").fill(english_name)
    page.get_by_role("textbox", name="field-name-pt").fill("Missão de teste e2e")
    page.get_by_role("textbox", name="field-description-en").fill(
        "e2e test description"
    )
    page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição da missão de teste"
    )
    page.get_by_role("textbox", name="field-relative_path").fill(
        "/somewhere/survey/mission"
    )


@pytest.mark.e2e
def test_survey_mission_lifecycle(authenticated_page: Page):
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("link", name="new-project").click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # create the survey mission
    authenticated_page.get_by_role("link", name="new-item").click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form(authenticated_page, mission_name)

    authenticated_page.get_by_role("button", name="add-another-link").click()
    authenticated_page.get_by_role("textbox", name="field-link-links-0-url").fill(
        "http://fakelink.com/somethings"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-media_type"
    ).fill("text/html")
    authenticated_page.get_by_role("textbox", name="field-link-links-0-relation").fill(
        "fake-relation"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description-en"
    ).fill("some link description")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description-pt"
    ).fill("uma descrição do link")

    authenticated_page.get_by_role("button", name="add-another-link").click()
    authenticated_page.get_by_role("textbox", name="field-link-links-1-url").fill(
        "http://fakelink2.com"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-media_type"
    ).fill("text/html")
    authenticated_page.get_by_role("textbox", name="field-link-links-1-relation").fill(
        "fake-relation2"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description-en"
    ).fill("some description for link 2")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description-pt"
    ).fill("uma descrição do segundo link")

    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )

    # clean up by deleting the survey mission, then the project
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()


@pytest.mark.e2e
def test_survey_mission_creation_rejects_duplicate_english_name(
    authenticated_page: Page,
):
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("link", name="new-project").click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )
    project_detail_url = authenticated_page.url

    # create the initial survey mission
    authenticated_page.get_by_role("link", name="new-item").click()
    mission_name = f"e2e duplicate mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form(authenticated_page, mission_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    # try to create another mission with the same english name under the same project
    authenticated_page.goto(project_detail_url)
    authenticated_page.get_by_role("link", name="new-item").click()
    _fill_survey_mission_form(authenticated_page, mission_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(
        authenticated_page.locator("#backend-validation-name-en-feedback")
    ).to_be_visible()

    # clean up: navigate to the mission detail page and delete it, then the project
    authenticated_page.goto(mission_detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()
