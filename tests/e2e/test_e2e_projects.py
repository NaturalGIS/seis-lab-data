import re
import uuid

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


def _fill_project_form(page: Page, english_name: str):
    page.get_by_role("textbox", name="field-name-en").fill(english_name)
    page.get_by_role("textbox", name="field-name-pt").fill("projeto de teste e2e")
    page.get_by_role("textbox", name="field-description-en").fill(
        "e2e test description"
    )
    page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição do projeto de teste"
    )
    page.get_by_role("textbox", name="field-root_path").fill("/somewhere")


@pytest.mark.e2e
def test_project_lifecycle(authenticated_page: Page):
    # start from the landing page
    authenticated_page.goto("/")

    project_name_id = uuid.uuid4().hex[:8]

    # navigate to the projects page and click the create new project button
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("link", name="new-project").click()

    # hit the cancel button and verify we are brought back to the projects page
    authenticated_page.get_by_role("link", name="cancel-creation").click()

    authenticated_page.get_by_role("link", name="new-project").click()

    # fill out the form and submit it — use a unique suffix to avoid collisions across runs
    project_name = f"e2e test project {project_name_id}"
    _fill_project_form(authenticated_page, project_name)

    authenticated_page.get_by_role("button", name="add-another-link").click()
    authenticated_page.get_by_role("textbox", name="field-link-links-0-url").fill(
        "http://fakelink.com"
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

    # expect to be redirected to the project detail page upon successful creation
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # try to modify the project, but this time hit the cancel button. This is done
    # before the real modification below because submitting a real update puts the
    # project into the `under_validation` status for a few seconds, during which the
    # `update-item` link is disabled - the status signal is only ever set once, when
    # the detail page is rendered, so clicking `update-item` again right after a real
    # update is racy (see issue tracking the live status/validation signal updates).
    authenticated_page.get_by_role("link", name="update-item").click()
    authenticated_page.get_by_role("link", name="cancel-update").click()

    # expect to be redirector the project detail page upon cancelling the modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # now actually modify the project
    authenticated_page.get_by_role("link", name="update-item").click()
    authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        f"The modified name {project_name_id}"
    )
    authenticated_page.get_by_role("button", name="submit-update-form").click()

    # expect to be redirector the project detail page upon successful modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # clean up by deleting the newly-created project
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()


@pytest.mark.e2e
def test_project_creation_rejects_duplicate_english_name(authenticated_page: Page):
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects").click()

    # create an initial project
    project_name = f"e2e duplicate test {uuid.uuid4().hex[:8]}"
    authenticated_page.get_by_role("link", name="new-project").click()
    _fill_project_form(authenticated_page, project_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # save the detail page URL so we can navigate back for cleanup
    detail_url = authenticated_page.url

    # navigate to the create form and submit with the same english name
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("link", name="new-project").click()
    _fill_project_form(authenticated_page, project_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # the form should re-render in place with an inline error on the english name field
    expect(
        authenticated_page.locator("#backend-validation-name-en-feedback")
    ).to_be_visible()

    # clean up by navigating to the detail page and deleting the project
    authenticated_page.goto(detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()
