import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.usefixtures("logged_in_user")
@pytest.mark.e2e
def test_project_lifecycle(page: Page):
    page.goto("/?lang=en")
    page.get_by_role("link", name=re.compile("projects", re.IGNORECASE)).click()
    page.get_by_role("link", name=re.compile("new project", re.IGNORECASE)).click()
    page.get_by_label(re.compile("english name", re.IGNORECASE)).fill(
        "e2e test project"
    )
    page.get_by_label(re.compile("portuguese name", re.IGNORECASE)).fill(
        "projeto de teste e2e"
    )
    page.get_by_label(re.compile("english description", re.IGNORECASE)).fill(
        "e2e test description"
    )
    page.get_by_label(re.compile("portuguese description", re.IGNORECASE)).fill(
        "descrição do projeto de teste"
    )
    page.get_by_label(re.compile("root path", re.IGNORECASE)).fill("/somewhere")
    page.get_by_role(
        "button", name=re.compile("add another link", re.IGNORECASE)
    ).click()
    page.locator("#links-0-url").fill("http://fakelink.com")
    page.locator("#links-0-media_type").fill("text/html")
    page.locator("#links-0-relation").fill("fake-relation")
    page.locator("#links-0-link_description-en").fill("some link description")
    page.locator("#links-0-link_description-pt").fill("uma descrição do link")
    page.get_by_role(
        "button", name=re.compile("add another link", re.IGNORECASE)
    ).click()
    page.locator("#links-1-url").fill("http://fakelink2.com")
    page.locator("#links-1-media_type").fill("text/html")
    page.locator("#links-1-relation").fill("fake-relation2")
    page.locator("#links-1-link_description-en").fill("some link description")
    page.locator("#links-1-link_description-pt").fill("uma descrição do link")
    page.get_by_role("button", name=re.compile("create project", re.IGNORECASE)).click()
    expect(
        page.get_by_text(re.compile("completed successfully", re.IGNORECASE))
    ).to_be_visible()

    # clean up by deleting the newly-created project
    page.get_by_role(
        "button", name=re.compile("delete project...", re.IGNORECASE)
    ).click()
    page.get_by_role(
        "button", name=re.compile("delete project$", re.IGNORECASE)
    ).click()
    expect(
        page.get_by_text(re.compile("completed successfully", re.IGNORECASE))
    ).to_be_visible()
