import pytest
from playwright.sync_api import (
    expect,
    Page,
)


@pytest.mark.e2e
def test_survey_related_record_lifecycle(shared_authenticated_page: Page):
    # NOTE: this test is perhaps overly long, but for now it covers the full creation
    # and deletion lifecycle of survey-related records. Let's revise later once
    # search functionality has been implemented.

    # Create a new project first, then a new survey mission under it
    # and finally a survey-related record under that

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

    shared_authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
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

    shared_authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
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
        shared_authenticated_page.get_by_test_id("processing-success-message")
    ).to_be_visible()

    # now create the new survey mission
    shared_authenticated_page.get_by_role("link", name="new-survey-mission").click()
    # fill out the form and submit it
    shared_authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        "e2e test survey mission"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-name-pt").fill(
        "Missão de teste e2e"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-en").fill(
        "e2e test description"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição da missão de teste"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-relative_path").fill(
        "/somewhere/survey/mission"
    )

    shared_authenticated_page.get_by_role(
        "button",
        name="add-another-link",
        exact=True,
    ).click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-url"
    ).fill("http://fakelink.com/somethings")
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

    shared_authenticated_page.get_by_role(
        "button",
        name="add-another-link",
        exact=True,
    ).click()
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

    # expect to see some confirmation that the survey mission was created
    expect(
        shared_authenticated_page.get_by_test_id("processing-success-message")
    ).to_be_visible()

    # now create a new survey-related record under that survey mission
    shared_authenticated_page.get_by_role(
        "link", name="new-survey-related-record"
    ).click()

    # fill out the form and submit it
    shared_authenticated_page.get_by_role("textbox", name="field-name-en").fill(
        "e2e test survey-related record"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-name-pt").fill(
        "Registo de teste e2e"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-en").fill(
        "e2e survey-related record description"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-description-pt").fill(
        "descrição do registo de teste"
    )
    shared_authenticated_page.get_by_role("textbox", name="field-relative_path").fill(
        "/somewhere/survey/related/record"
    )
    shared_authenticated_page.get_by_role(
        "button",
        name="add-another-link",
        exact=True,
    ).click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-url"
    ).fill("http://fakelink.com/for/record")
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

    shared_authenticated_page.get_by_role(
        "button",
        name="add-another-link",
        exact=True,
    ).click()
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

    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-name-en"
    ).fill("Sample e2e asset")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-name-pt"
    ).fill("Recurso de teste e2e")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-description-en"
    ).fill("This is a sample asset used in e2e tests")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-description-pt"
    ).fill("Este é um recurso de test usado em testes e2e")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-relative_path"
    ).fill("/asset/relative/path")
    shared_authenticated_page.get_by_role(
        "button", name="asset-0-add-another-link"
    ).click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-url"
    ).fill("http://fakelink.com/for/record")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-media_type"
    ).fill("text/html")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-relation"
    ).fill("fake-relation")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-assets-0-links-0-link_description-en"
    ).fill("some link description")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-assets-0-links-0-link_description-pt"
    ).fill("uma descrição do link")

    shared_authenticated_page.get_by_role("button", name="add-another-asset").click()

    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-name-en"
    ).fill("Sample e2e second asset")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-name-pt"
    ).fill("Segundo recurso de teste e2e")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-description-en"
    ).fill("This the second sample asset used in e2e tests")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-description-pt"
    ).fill("Este é um segundo recurso de test usado em testes e2e")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-relative_path"
    ).fill("/asset/relative/path")
    shared_authenticated_page.get_by_role(
        "button", name="asset-1-add-another-link"
    ).click()
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-url"
    ).fill("http://fakelink.com/for/record")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-media_type"
    ).fill("text/html")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-relation"
    ).fill("fake-relation")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-assets-1-links-0-link_description-en"
    ).fill("some link description")
    shared_authenticated_page.get_by_role(
        "textbox", name="field-link-assets-1-links-0-link_description-pt"
    ).fill("uma descrição do link")

    shared_authenticated_page.get_by_role("button", name="submit-create-form").click()

    # expect to see some confirmation that the survey mission was created
    expect(
        shared_authenticated_page.get_by_test_id("processing-success-message")
    ).to_be_visible()

    # clean up by deleting the newly-created survey-related record
    shared_authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    shared_authenticated_page.get_by_role(
        "button", name="delete-survey-related-record"
    ).click()
    expect(
        shared_authenticated_page.get_by_role("link", name="new-survey-related-record")
    ).to_be_visible()

    # and then delete also the newly-created survey mission
    shared_authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    shared_authenticated_page.get_by_role(
        "button", name="delete-survey-mission"
    ).click()
    expect(
        shared_authenticated_page.get_by_role("link", name="new-survey-mission")
    ).to_be_visible()

    # and then delete also the also newly-created project
    shared_authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    shared_authenticated_page.get_by_role("button", name="delete-project").click()
    expect(
        shared_authenticated_page.get_by_role("link", name="new-project")
    ).to_be_visible()
