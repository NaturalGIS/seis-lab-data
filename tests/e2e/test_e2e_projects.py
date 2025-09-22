import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_project_lifecycle(shared_authenticated_page: Page):
    shared_authenticated_page.goto("/")
    shared_authenticated_page.get_by_test_id("projects-nav").click()
    shared_authenticated_page.get_by_test_id("new-project-nav").click()
    shared_authenticated_page.get_by_label(
        re.compile("english name", re.IGNORECASE)
    ).fill("e2e test project")
    shared_authenticated_page.get_by_label(
        re.compile("portuguese name", re.IGNORECASE)
    ).fill("projeto de teste e2e")
    shared_authenticated_page.get_by_label(
        re.compile("english description", re.IGNORECASE)
    ).fill("e2e test description")
    shared_authenticated_page.get_by_label(
        re.compile("portuguese description", re.IGNORECASE)
    ).fill("descrição do projeto de teste")
    shared_authenticated_page.get_by_label(
        re.compile("root\wpath", re.IGNORECASE)
    ).fill("/somewhere")
    shared_authenticated_page.get_by_role(
        "button", name=re.compile("add another link", re.IGNORECASE)
    ).click()
    shared_authenticated_page.locator("#links-0-url").fill("http://fakelink.com")
    shared_authenticated_page.locator("#links-0-media_type").fill("text/html")
    shared_authenticated_page.locator("#links-0-relation").fill("fake-relation")
    shared_authenticated_page.locator("#links-0-link_description-en").fill(
        "some link description"
    )
    shared_authenticated_page.locator("#links-0-link_description-pt").fill(
        "uma descrição do link"
    )
    shared_authenticated_page.get_by_role(
        "button", name=re.compile("add another link", re.IGNORECASE)
    ).click()
    shared_authenticated_page.locator("#links-1-url").fill("http://fakelink2.com")
    shared_authenticated_page.locator("#links-1-media_type").fill("text/html")
    shared_authenticated_page.locator("#links-1-relation").fill("fake-relation2")
    shared_authenticated_page.locator("#links-1-link_description-en").fill(
        "some link description"
    )
    shared_authenticated_page.locator("#links-1-link_description-pt").fill(
        "uma descrição do link"
    )
    shared_authenticated_page.get_by_role(
        "button", name=re.compile("create project", re.IGNORECASE)
    ).click()
    expect(
        shared_authenticated_page.get_by_text(
            re.compile("completed successfully", re.IGNORECASE)
        )
    ).to_be_visible()

    # clean up by deleting the newly-created project
    shared_authenticated_page.get_by_role(
        "button", name=re.compile("delete project...", re.IGNORECASE)
    ).click()
    shared_authenticated_page.get_by_role(
        "button", name=re.compile("delete project$", re.IGNORECASE)
    ).click()
    expect(shared_authenticated_page.get_by_test_id("new-project-nav")).to_be_visible()
