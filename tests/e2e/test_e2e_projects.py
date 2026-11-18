"""Managing projects in the browser

An editor creates, modifies and deletes projects through the web forms, and the list of
projects behaves consistently as projects are removed.
"""

import re
import uuid

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


def _fill_project_form(page: Page, name: str):
    page.get_by_role("textbox", name="field-name").fill(name)
    page.get_by_role("textbox", name="field-description").fill("e2e test description")


@pytest.mark.e2e
def test_project_lifecycle(authenticated_page: Page):
    """An editor opens and cancels the creation form, creates a project with a
    description and two links, opens and cancels the modification form, renames the
    project and deletes it. The deletion confirmation names the project.
    """
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
        "textbox", name="field-link-links-0-link_description"
    ).fill("some link description")

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
        "textbox", name="field-link-links-1-link_description"
    ).fill("some description for link 2")

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
    authenticated_page.get_by_role("textbox", name="field-name").fill(
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
    # the confirmation dialog names the item about to be deleted
    expect(authenticated_page.get_by_role("dialog")).to_contain_text(
        f"“The modified name {project_name_id}”"
    )
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()


@pytest.mark.e2e
def test_project_creation_rejects_duplicate_name(authenticated_page: Page):
    """Creating a project with the name of an existing project is refused, and the form
    shows an error next to the name field.
    """
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

    # navigate to the create form and submit with the same name
    authenticated_page.get_by_role("link", name="list-projects").click()
    authenticated_page.get_by_role("link", name="new-project").click()
    _fill_project_form(authenticated_page, project_name)
    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # the form should re-render in place with an inline error on the name field
    expect(
        authenticated_page.locator("#backend-validation-name-feedback")
    ).to_be_visible()

    # clean up by navigating to the detail page and deleting the project
    authenticated_page.goto(detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal"
    ).click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(authenticated_page.get_by_role("link", name="new-project")).to_be_visible()


@pytest.mark.e2e
def test_deleting_listed_item_keeps_current_page(authenticated_page: Page):
    """While the second page of the list of projects is shown, projects deleted
    elsewhere disappear from it and the list stays on that page; once its last project
    is deleted, the list returns to the first page.
    """
    # the listing page size defaults to 20: two items on the second page
    tag = uuid.uuid4().hex[:8]
    detail_urls = []
    for index in range(22):
        authenticated_page.goto("/projects/new")
        _fill_project_form(authenticated_page, f"e2e paging {tag} {index:02d}")
        authenticated_page.get_by_role("button", name="submit-create-form").click()
        expect(authenticated_page).to_have_url(
            re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
        )
        detail_urls.append(authenticated_page.url)

    # projects are deleted from their detail page, in another tab, while the
    # listing re-fetches its items whenever a project is deleted
    deletion_page = authenticated_page.context.new_page()

    def delete_project(detail_url: str) -> None:
        deletion_page.goto(detail_url)
        deletion_page.get_by_role(
            "button", name="show-delete-confirmation-modal"
        ).click()
        deletion_page.get_by_role("button", name="delete-item").click()
        expect(deletion_page).to_have_url(re.compile(r"/projects/?$"), timeout=10_000)

    authenticated_page.goto(f"/projects/?search=e2e+paging+{tag}&page=2")
    # each listed project's name links to its detail page
    name_links = authenticated_page.locator("[aria-label='items']").get_by_role(
        "link", name=re.compile(f"e2e paging {tag}")
    )
    expect(name_links).to_have_count(2)

    # deleting an item re-fetches the listing, which stays on the second page
    delete_project(detail_urls.pop())
    expect(name_links).to_have_count(1, timeout=10_000)
    expect(authenticated_page).to_have_url(re.compile(r"[?&]page=2(&|$)"))

    # deleting the last item of the second page falls back to the first one
    delete_project(detail_urls.pop())
    expect(name_links).to_have_count(20, timeout=10_000)
    expect(authenticated_page).not_to_have_url(re.compile(r"[?&]page="))

    # clean up the remaining projects
    for detail_url in detail_urls:
        delete_project(detail_url)
    expect(name_links).to_have_count(0, timeout=10_000)
