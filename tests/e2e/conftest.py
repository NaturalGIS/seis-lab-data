import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


def pytest_addoption(parser):
    parser.addoption("--user-email")
    parser.addoption("--user-password")


def pytest_generate_tests(metafunc):
    if "user_email" in metafunc.fixturenames:
        metafunc.parametrize("user_email", [metafunc.config.getoption("user_email")])
    if "user_password" in metafunc.fixturenames:
        metafunc.parametrize(
            "user_password", [metafunc.config.getoption("user_password")]
        )


@pytest.fixture
def logged_in_user(page: Page, user_email: str, user_password: str):
    page.goto("/?lang=en")
    page.get_by_text(re.compile("login", re.IGNORECASE)).click()
    page.get_by_placeholder(re.compile("email", re.IGNORECASE)).fill(user_email)
    page.get_by_placeholder(
        re.compile("please enter your password", re.IGNORECASE)
    ).fill(user_password)
    page.get_by_text(re.compile("log in", re.IGNORECASE)).click()
    expect(page.get_by_text(re.compile("logout", re.IGNORECASE))).to_be_visible()
    yield
