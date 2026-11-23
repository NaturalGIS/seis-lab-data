"""Managing dataset categories in the browser

An editor creates, renames and deletes dataset categories from the settings menu.
"""

import re
import uuid

import pytest
from playwright.sync_api import (
    Locator,
    Page,
    expect,
)


def _fill_dataset_category_form(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)


def _find_dataset_category_card(page: Page, name: str) -> Locator:
    """Locate the listing-page card for a given dataset category.

    Dataset categories have no dedicated detail page — every action (view, edit,
    delete) happens from the listing page, which is paginated and sorted by name
    rather than by creation time. Filtering through the search box narrows the
    list down to the single matching item, which makes the card easy to find
    regardless of pagination/ordering, and also means only one delete-confirmation
    modal is present in the DOM when the delete button is clicked.
    """
    page.get_by_role("searchbox", name="Search dataset categories", exact=True).fill(
        name
    )
    card = page.locator(".card", has_text=name)
    expect(card).to_be_visible(timeout=10_000)
    return card


@pytest.mark.e2e
def test_dataset_category_lifecycle(authenticated_page: Page):
    """An editor opens and cancels the creation form, creates a dataset category,
    renames it, opens and cancels the modification form, and deletes it. The deletion
    confirmation names the dataset category.
    """
    # start from the landing page
    authenticated_page.goto("/")

    resource_name_id = uuid.uuid4().hex[:8]

    # navigate to the dataset categories page and click the create new button
    authenticated_page.get_by_role("button", name="Settings", exact=True).click()
    authenticated_page.get_by_role(
        "link", name="list-dataset-categories", exact=True
    ).click()
    authenticated_page.get_by_role(
        "link", name="new-dataset-category", exact=True
    ).click()

    # hit the cancel button and verify we are brought back to the listing page
    authenticated_page.get_by_role("link", name="cancel-creation", exact=True).click()

    authenticated_page.get_by_role(
        "link", name="new-dataset-category", exact=True
    ).click()

    # fill out the form and submit it — use a unique suffix to avoid collisions across runs
    category_name = f"e2e test dataset category {resource_name_id}"
    _fill_dataset_category_form(authenticated_page, category_name)

    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()

    # expect to be redirected to the listing page upon successful creation
    expect(authenticated_page).to_have_url(
        re.compile(r"/dataset-categories/$"), timeout=10_000
    )

    # find the newly-created category and open its edit form
    card = _find_dataset_category_card(authenticated_page, category_name)
    card.get_by_role("link").click()

    updated_category_name = f"{category_name} (updated)"
    _fill_dataset_category_form(authenticated_page, updated_category_name)
    authenticated_page.get_by_role(
        "button", name="submit-update-form", exact=True
    ).click()

    # expect to be redirected to the listing page upon successful modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/dataset-categories/$"), timeout=10_000
    )
    card = _find_dataset_category_card(authenticated_page, category_name)

    # now try to modify the category again, but this time hit the cancel button
    card.get_by_role("link").click()
    authenticated_page.get_by_role("link", name="cancel-update", exact=True).click()

    # expect to be redirected to the listing page upon cancelling the modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/dataset-categories/$"), timeout=10_000
    )

    # clean up by deleting the newly-created category
    card = _find_dataset_category_card(authenticated_page, category_name)
    card.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    # the confirmation dialog names the item about to be deleted
    expect(authenticated_page.get_by_role("dialog")).to_contain_text(
        f"“{updated_category_name}”"
    )
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(card).not_to_be_visible()


@pytest.mark.e2e
def test_dataset_category_creation_rejects_duplicate_name(
    authenticated_page: Page,
):
    """Creating a dataset category with the name of an existing one is refused, and the
    form shows an error next to the name field.
    """
    authenticated_page.goto("/")
    authenticated_page.get_by_role("button", name="Settings", exact=True).click()
    authenticated_page.get_by_role(
        "link", name="list-dataset-categories", exact=True
    ).click()

    # create an initial category
    resource_name_id = uuid.uuid4().hex[:8]
    category_name = f"e2e duplicate test {resource_name_id}"
    authenticated_page.get_by_role(
        "link", name="new-dataset-category", exact=True
    ).click()
    _fill_dataset_category_form(authenticated_page, category_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/dataset-categories/$"), timeout=10_000
    )

    # navigate to the create form and submit with the same name
    authenticated_page.get_by_role(
        "link", name="new-dataset-category", exact=True
    ).click()
    _fill_dataset_category_form(authenticated_page, category_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()

    # the form should re-render in place with an inline error on the name field
    expect(
        authenticated_page.locator("#backend-validation-name-feedback")
    ).to_be_visible()

    # clean up by navigating back to the listing page and deleting the category
    authenticated_page.get_by_role("link", name="cancel-creation", exact=True).click()
    card = _find_dataset_category_card(authenticated_page, category_name)
    card.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(card).not_to_be_visible()
