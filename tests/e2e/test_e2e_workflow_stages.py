import re
import uuid

import pytest
from playwright.sync_api import (
    Locator,
    Page,
    expect,
)


def _fill_workflow_stage_form(page: Page, name: str):
    page.get_by_role("textbox", name="field-name").fill(name)


def _find_workflow_stage_card(page: Page, name: str) -> Locator:
    """Locate the listing-page card for a given workflow stage.

    Workflow stages have no dedicated detail page — every action (view, edit,
    delete) happens from the listing page, which is paginated and sorted by name
    rather than by creation time. Filtering through the search box narrows the
    list down to the single matching item, which makes the card easy to find
    regardless of pagination/ordering, and also means only one delete-confirmation
    modal is present in the DOM when the delete button is clicked.
    """
    page.get_by_role("searchbox", name="search workflow stages").fill(name)
    card = page.locator(".card", has_text=name)
    expect(card).to_be_visible(timeout=10_000)
    return card


@pytest.mark.e2e
def test_workflow_stage_lifecycle(authenticated_page: Page):
    # start from the landing page
    authenticated_page.goto("/")

    resource_name_id = uuid.uuid4().hex[:8]

    # navigate to the workflow stages page and click the create new button
    authenticated_page.get_by_role("button", name="settings").click()
    authenticated_page.get_by_role("link", name="list-workflow-stages").click()
    authenticated_page.get_by_role("link", name="new-workflow-stage").click()

    # hit the cancel button and verify we are brought back to the listing page
    authenticated_page.get_by_role("link", name="cancel-creation").click()

    authenticated_page.get_by_role("link", name="new-workflow-stage").click()

    # fill out the form and submit it — use a unique suffix to avoid collisions across runs
    stage_name = f"e2e test workflow stage {resource_name_id}"
    _fill_workflow_stage_form(authenticated_page, stage_name)

    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # expect to be redirected to the listing page upon successful creation
    expect(authenticated_page).to_have_url(
        re.compile(r"/workflow-stages/$"), timeout=10_000
    )

    # find the newly-created stage and open its edit form
    card = _find_workflow_stage_card(authenticated_page, stage_name)
    card.get_by_role("link").click()

    updated_stage_name = f"{stage_name} (updated)"
    _fill_workflow_stage_form(authenticated_page, updated_stage_name)
    authenticated_page.get_by_role("button", name="submit-update-form").click()

    # expect to be redirected to the listing page upon successful modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/workflow-stages/$"), timeout=10_000
    )
    card = _find_workflow_stage_card(authenticated_page, stage_name)

    # now try to modify the stage again, but this time hit the cancel button
    card.get_by_role("link").click()
    authenticated_page.get_by_role("link", name="cancel-update").click()

    # expect to be redirected to the listing page upon cancelling the modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/workflow-stages/$"), timeout=10_000
    )

    # clean up by deleting the newly-created stage
    card = _find_workflow_stage_card(authenticated_page, stage_name)
    card.get_by_role("button", name="show-delete-confirmation-modal").click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(card).not_to_be_visible()


@pytest.mark.e2e
def test_workflow_stage_creation_rejects_duplicate_name(
    authenticated_page: Page,
):
    authenticated_page.goto("/")
    authenticated_page.get_by_role("button", name="settings").click()
    authenticated_page.get_by_role("link", name="list-workflow-stages").click()

    # create an initial stage
    resource_name_id = uuid.uuid4().hex[:8]
    stage_name = f"e2e duplicate test {resource_name_id}"
    authenticated_page.get_by_role("link", name="new-workflow-stage").click()
    _fill_workflow_stage_form(authenticated_page, stage_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/workflow-stages/$"), timeout=10_000
    )

    # navigate to the create form and submit with the same name
    authenticated_page.get_by_role("link", name="new-workflow-stage").click()
    _fill_workflow_stage_form(authenticated_page, stage_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # the form should re-render in place with an inline error on the name field
    expect(
        authenticated_page.locator("#backend-validation-name-feedback")
    ).to_be_visible()

    # clean up by navigating back to the listing page and deleting the stage
    authenticated_page.get_by_role("link", name="cancel-creation").click()
    card = _find_workflow_stage_card(authenticated_page, stage_name)
    card.get_by_role("button", name="show-delete-confirmation-modal").click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(card).not_to_be_visible()
