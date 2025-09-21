import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_login(page: Page, user_email: str, user_password: str):
    page.goto("/?lang=en")
    page.get_by_text(re.compile("login", re.IGNORECASE)).click()
    page.get_by_placeholder(re.compile("email", re.IGNORECASE)).fill(user_email)
    page.get_by_placeholder(
        re.compile("please enter your password", re.IGNORECASE)
    ).fill(user_password)
    page.get_by_text(re.compile("log in", re.IGNORECASE)).click()
    expect(page.get_by_text(re.compile("logout", re.IGNORECASE))).to_be_visible()
