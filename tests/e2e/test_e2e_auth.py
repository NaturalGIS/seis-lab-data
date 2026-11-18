"""Logging in and out in the browser

Users authenticate through the login page and can end their session from the user menu.
"""

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_login(authenticated_page: Page):
    """A user logs in with their credentials and the home page then shows their user
    menu.
    """
    authenticated_page.goto("/")
    expect(authenticated_page.get_by_test_id("user-menu")).to_be_visible()


@pytest.mark.e2e
def test_logout(fresh_authenticated_page: Page):
    """A logged-in user opens the user menu and logs out."""
    fresh_authenticated_page.goto("/")
    fresh_authenticated_page.get_by_role("button", name="user-menu-toggle").click()
    fresh_authenticated_page.get_by_role("menu", name="user-menu").get_by_role(
        "link", name="logout-nav"
    ).click()
