"""Logging in and out in the browser

Users authenticate through the login page and can end their session from the user menu.
"""

import re

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
def test_logout(fresh_authenticated_page: Page, base_url: str):
    """A logged-in user opens the user menu and logs out, after which they are
    brought back to the landing page as an anonymous user, and logging in again
    requires entering their credentials.
    """
    fresh_authenticated_page.goto("/")
    fresh_authenticated_page.get_by_role(
        "button", name="user-menu-toggle", exact=True
    ).click()
    fresh_authenticated_page.get_by_role(
        "menu", name="user-menu", exact=True
    ).get_by_role("link", name="logout-nav", exact=True).click()
    expect(fresh_authenticated_page).to_have_url(
        f"{base_url.rstrip('/')}/", timeout=30_000
    )
    expect(fresh_authenticated_page.get_by_test_id("login-nav")).to_be_visible()
    expect(fresh_authenticated_page.get_by_test_id("user-menu")).to_have_count(0)
    fresh_authenticated_page.get_by_test_id("login-nav").click()
    expect(
        fresh_authenticated_page.get_by_placeholder(re.compile("email", re.IGNORECASE))
    ).to_be_visible(timeout=60_000)
