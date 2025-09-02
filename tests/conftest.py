import pytest
import pytest_asyncio

import sqlmodel
from starlette.testclient import TestClient

from seis_lab_data import config
from seis_lab_data.cliapp import (
    bootstrapdata,
    sampledata,
)
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
async def bootstrap_dataset_categories(db, db_session_maker):
    created = []
    async with db_session_maker() as session:
        for category_to_create in bootstrapdata.DATASET_CATEGORIES_TO_CREATE:
            created.append(
                await commands.create_dataset_category(session, category_to_create)
            )
    yield created


@pytest_asyncio.fixture
async def bootstrap_domain_types(db, db_session_maker):
    created = []
    async with db_session_maker() as session:
        for domain_to_create in bootstrapdata.DOMAIN_TYPES_TO_CREATE:
            created.append(await commands.create_domain_type(session, domain_to_create))
    yield created


@pytest_asyncio.fixture
async def bootstrap_workflow_stages(db, db_session_maker):
    created = []
    async with db_session_maker() as session:
        for stage_to_create in bootstrapdata.WORKFLOW_STAGES_TO_CREATE:
            created.append(
                await commands.create_workflow_stage(session, stage_to_create)
            )
    yield created


@pytest_asyncio.fixture
async def sample_projects(db, db_session_maker):
    created = []
    async with db_session_maker() as session:
        for project_to_create in sampledata.get_projects_to_create():
            created.append(await commands.create_project(session, project_to_create))
    yield created


@pytest_asyncio.fixture
async def sample_survey_missions(db, db_session_maker, sample_projects):
    created = []
    async with db_session_maker() as session:
        for survey_mission_to_create in sampledata.get_survey_missions_to_create():
            created.append(
                await commands.create_survey_mission(session, survey_mission_to_create)
            )
    yield created


@pytest_asyncio.fixture
async def sample_survey_related_records(
    db,
    db_session_maker,
    sample_survey_missions,
    bootstrap_dataset_categories,
    bootstrap_domain_types,
    bootstrap_workflow_stages,
):
    created = []
    async with db_session_maker() as session:
        for survey_record_to_create in sampledata.get_survey_related_records_to_create(
            dataset_categories={c.name["en"]: c for c in bootstrap_dataset_categories},
            domain_types={d.name["en"]: d for d in bootstrap_domain_types},
            workflow_stages={w.name["en"]: w for w in bootstrap_workflow_stages},
        ):
            created.append(
                await commands.create_survey_related_record(
                    session, survey_record_to_create
                )
            )
    yield created
