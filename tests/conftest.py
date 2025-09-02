import pytest
import pytest_asyncio

import sqlmodel
from starlette.testclient import TestClient

from seis_lab_data import config
from seis_lab_data.cliapp import sampledata
from seis_lab_data.db.engine import (
    get_engine,
    get_session_maker,
    get_sync_engine,
)
from seis_lab_data.db import commands
from seis_lab_data.webapp.app import create_app_from_settings


@pytest.fixture
def settings():
    original_settings = config.get_settings()
    original_settings.message_broker_dsn = None
    original_settings.database_dsn = original_settings.test_database_dsn
    return original_settings


@pytest.fixture
def sync_db_engine(settings: config.SeisLabDataSettings):
    yield get_sync_engine(settings)


@pytest.fixture()
def db_engine(settings: config.SeisLabDataSettings):
    yield get_engine(settings)


@pytest.fixture()
def db_session_maker(db_engine):
    yield get_session_maker(db_engine)


@pytest.fixture()
def db(sync_db_engine):
    """Provides a clean database."""
    sqlmodel.SQLModel.metadata.create_all(sync_db_engine)
    yield
    sqlmodel.SQLModel.metadata.drop_all(sync_db_engine)


@pytest.fixture
def app(settings):
    return create_app_from_settings(settings)


@pytest.fixture
def test_client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def sample_projects(db, db_session_maker):
    created = []
    async with db_session_maker() as session:
        for project_to_create in sampledata.PROJECTS_TO_CREATE:
            created.append(await commands.create_project(session, project_to_create))
    yield created


@pytest_asyncio.fixture
async def sample_survey_missions(db, db_session_maker, sample_projects):
    created = []
    async with db_session_maker() as session:
        for survey_mission_to_create in sampledata.SURVEY_MISSIONS_TO_CREATE:
            created.append(
                await commands.create_survey_mission(session, survey_mission_to_create)
            )
    yield created
