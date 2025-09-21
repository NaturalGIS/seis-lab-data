import re

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
def test_webapp_login(page: Page):
    page.goto("/?lang=en")
    page.get_by_text(re.compile("login", re.IGNORECASE)).click()
    page.get_by_text(re.compile("email", re.IGNORECASE)).fill("akadmin@email.com")
    page.get_by_text(re.compile("password", re.IGNORECASE)).fill("admin123")
    page.get_by_text(re.compile("login", re.IGNORECASE)).click()
    expect(page.get_by_text("authentik Default admin")).to_be_visible()
