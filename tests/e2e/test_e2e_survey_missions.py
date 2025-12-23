import pytest
from playwright.sync_api import (
    expect,
    Page,
)


@pytest.mark.e2e
def test_survey_mission_lifecycle(authenticated_page: Page):
    # Create a new project first, then a new survey mission under it

    # start from the landing page
    authenticated_page.goto("/")

    # navigate to the projects page and click the create new project button
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("button", name="new-project").click()

    # fill out the form and submit it
    authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        "e2e test project"
    )

    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # expect to see some confirmation that the project was created
    expect(
        authenticated_page.get_by_test_id("processing-success-message")
    ).to_be_visible(timeout=10_000)

    # now create the new survey mission
    authenticated_page.get_by_role("button", name="new-item").click()
    # fill out the form and submit it
    authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        "e2e test survey mission"
    )
    authenticated_page.get_by_role("textbox", name="field-name-pt").fill(
        "Missão de teste e2e"
    )
    authenticated_page.get_by_role("textbox", name="field-description-en").fill(
        "e2e test description"
    )
    authenticated_page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição da missão de teste"
    )
    authenticated_page.get_by_role("textbox", name="field-relative_path").fill(
        "/somewhere/survey/mission"
    )

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

    # expect to see some confirmation that the survey mission was created
    expect(
        authenticated_page.get_by_test_id("processing-success-message")
    ).to_be_visible(timeout=10_000)

    # clean up by deleting the newly-created survey mission
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("button", name="new-item")).to_be_visible()

    # and then delete also the also newly-created project
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("button", name="new-project")).to_be_visible()
