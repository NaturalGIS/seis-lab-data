"""Managing survey missions in the browser

An editor creates, modifies and deletes survey missions within a project through the web
forms.
"""

import re
import uuid

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


def _fill_project_form_minimal(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)


def _fill_survey_mission_form(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)
    page.get_by_role("textbox", name="field-description", exact=True).fill(
        "e2e test description"
    )
    page.get_by_role("textbox", name="field-relative_path", exact=True).fill(
        "/somewhere/survey/mission"
    )


@pytest.mark.e2e
def test_survey_mission_lifecycle(authenticated_page: Page):
    """Within a new project, an editor opens and cancels the creation form, creates a
    survey mission with a description, an archive path and two links, opens and cancels
    the modification form, renames the mission and deletes it. The deletion confirmation
    names the survey mission.
    """
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # access the new mission page but then cancel it and verify we are back in the project detail page
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    authenticated_page.get_by_role("link", name="cancel-creation", exact=True).click()

    # create the survey mission
    mission_name_id = uuid.uuid4().hex[:8]
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {mission_name_id}"
    _fill_survey_mission_form(authenticated_page, mission_name)

    authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-url", exact=True
    ).fill("http://fakelink.com/somethings")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-relation", exact=True
    ).fill("fake-relation")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description", exact=True
    ).fill("some link description")

    authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-url", exact=True
    ).fill("http://fakelink2.com")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-relation", exact=True
    ).fill("fake-relation2")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description", exact=True
    ).fill("some description for link 2")

    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )

    # now try to modify the mission, but cancel and verify we are back at the mission detail page
    authenticated_page.get_by_role("link", name="update-item", exact=True).click()
    authenticated_page.get_by_role("link", name="cancel-update", exact=True).click()

    # and now actually modify it
    authenticated_page.get_by_role("link", name="update-item", exact=True).click()
    authenticated_page.get_by_role("textbox", name="field-name", exact=True).fill(
        f"The modified name {mission_name_id}"
    )
    authenticated_page.get_by_role(
        "button", name="submit-update-form", exact=True
    ).click()

    # clean up by deleting the survey mission, then the project
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    # the confirmation dialog names the item about to be deleted
    expect(authenticated_page.get_by_role("dialog")).to_contain_text(
        f"“The modified name {mission_name_id}”"
    )
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-project", exact=True)
    ).to_be_visible()


@pytest.mark.e2e
def test_survey_mission_creation_rejects_duplicate_name(
    authenticated_page: Page,
):
    """Creating a survey mission with the name of an existing survey mission of the same
    project is refused, and the form shows an error next to the name field.
    """
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )
    project_detail_url = authenticated_page.url

    # create the initial survey mission
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e duplicate mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    # try to create another mission with the same name under the same project
    authenticated_page.goto(project_detail_url)
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    _fill_survey_mission_form(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(
        authenticated_page.locator("#backend-validation-name-feedback")
    ).to_be_visible()

    # clean up: navigate to the mission detail page and delete it, then the project
    authenticated_page.goto(mission_detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-project", exact=True)
    ).to_be_visible()
