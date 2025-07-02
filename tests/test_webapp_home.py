import pytest
from playwright.sync_api import (
    Page,
    expect,
)
from starlette.testclient import TestClient

from seis_lab_data.config import SeisLabDataSettings


def test_home_contains_message(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    target_message = "Hello, world!"
    assert target_message in response.text


@pytest.mark.e2e
def test_webapp_home_is_up(settings: SeisLabDataSettings, page: Page):
    page.goto("/")
    # NOTE: the below is a bad example of how to use playwright locators
    # this is intended just as an initial placeholder test though
    locator = page.locator("body > div.container > div.row > p")
    expect(locator).to_have_text("Hello, world!")
