import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_webapp_home_is_up(page: Page):
    page.goto("/")
    # NOTE: the below is a bad example of how to use playwright locators
    # this is intended just as an initial placeholder test though
    locator = page.locator("body > div.container > div.row > p")
    expect(locator).to_have_text("Hello, world!")
