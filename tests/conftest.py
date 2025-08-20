import pytest
import seis_lab_data.config
from starlette.testclient import TestClient

from seis_lab_data.webapp.app import create_app_from_settings


@pytest.fixture
def settings():
    original_settings = seis_lab_data.config.get_settings()
    original_settings.message_broker_dsn = None
    return original_settings


@pytest.fixture
def app(settings):
    return create_app_from_settings(settings)


@pytest.fixture
def test_client(app):
    with TestClient(app) as test_client:
        yield test_client
