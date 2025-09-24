import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_login(shared_authenticated_page: Page):
    shared_authenticated_page.goto("/")
    expect(shared_authenticated_page.get_by_test_id("user-menu")).to_be_visible()


@pytest.mark.e2e
def test_logout(fresh_authenticated_page: Page):
    fresh_authenticated_page.goto("/")
    fresh_authenticated_page.get_by_test_id("logout-nav").click()
