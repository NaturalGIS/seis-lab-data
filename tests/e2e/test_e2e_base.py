import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_webapp_home_is_up(page: Page):
    page.goto("/?lang=en")
    # NOTE: the below is a bad example of how to use playwright locators
    # this is intended just as an initial placeholder test though
    locator = page.locator("body > div.container-fluid > div.row > p:last-child")
    expect(locator).to_have_text("Hi there!")


@pytest.mark.e2e
def test_set_language(page: Page):
    page.goto("/")
    page.get_by_role("button", name="toggle-lang").click()
    page.get_by_role("link", name="set-lang-en").click()
    expect(page.get_by_role("link", name="list-projects")).to_have_text("Projects")
    page.get_by_role("button", name="toggle-lang").click()
    page.get_by_role("link", name="set-lang-pt").click()
    expect(page.get_by_role("link", name="list-projects")).to_have_text("Projetos")
