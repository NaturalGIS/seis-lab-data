import re

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


@pytest.mark.e2e
def test_webapp_home_is_up(page: Page):
    page.goto("/?lang=en")
    expect(page.get_by_label("title")).to_have_text("SeisLabData")
    expect(page.get_by_role("heading", name="Recent missions")).to_be_visible()


@pytest.mark.e2e
def test_set_language(page: Page):
    page.goto("/")
    page.get_by_role("button", name="toggle-lang").click()
    page.get_by_role("link", name="set-lang-en").click()
    expect(page.get_by_role("link", name="list-projects")).to_contain_text(
        re.compile("Projects")
    )
    page.get_by_role("button", name="toggle-lang").click()
    page.get_by_role("link", name="set-lang-pt").click()
    expect(page.get_by_role("link", name="list-projects")).to_contain_text(
        re.compile("Projetos")
    )
