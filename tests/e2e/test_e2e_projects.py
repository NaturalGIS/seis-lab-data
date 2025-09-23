import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_project_lifecycle(shared_authenticated_page: Page):
    # start from the landing page
    shared_authenticated_page.goto("/")

    # navigate to the projects page and click the create new project button
    shared_authenticated_page.get_by_role("link", name="list-projects").click()
    shared_authenticated_page.get_by_role("link", name="new-project").click()

    # fill out the form and submit it
    shared_authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        "e2e test project"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-name-pt").fill(
        "projeto de teste e2e"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-en").fill(
        "e2e test description"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição do projeto de teste"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-root_path").fill(
        "/somewhere"
    )

    shared_authenticated_page.get_by_role("button", name="add-another-link").click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-url"
    ).fill("http://fakelink.com")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-media_type"
    ).fill("text/html")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-relation"
    ).fill("fake-relation")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description-en"
    ).fill("some link description")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description-pt"
    ).fill("uma descrição do link")

    shared_authenticated_page.get_by_role("button", name="add-another-link").click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-url"
    ).fill("http://fakelink2.com")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-media_type"
    ).fill("text/html")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-relation"
    ).fill("fake-relation2")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description-en"
    ).fill("some description for link 2")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description-pt"
    ).fill("uma descrição do segundo link")

    shared_authenticated_page.get_by_role("button", name="submit-create-form").click()

    # expect to see some confirmation that the project was created
    expect(
        shared_authenticated_page.get_by_text(
            re.compile("completed successfully", re.IGNORECASE)
        )
    ).to_be_visible()

    # clean up by deleting the newly-created project
    shared_authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    shared_authenticated_page.get_by_role("button", name="delete-project").click()
    expect(
        shared_authenticated_page.get_by_role("link", name="new-project")
    ).to_be_visible()
