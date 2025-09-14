import uuid

import pytest

from seis_lab_data.db import (
    commands,
    queries,
)
from seis_lab_data import schemas


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_dataset_category(db, db_session_maker):
    to_create = schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("303cad6d-2e0e-447e-85e1-c284c1c882a7")),
        name=schemas.LocalizableDraftName(en="A fake category"),
    )
    async with db_session_maker() as session:
        created = await commands.create_dataset_category(session, to_create)
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name["en"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_dataset_category(db, db_session_maker):
    to_create = schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("26b06713-dce1-4304-bf50-fec5c3f5efe6")),
        name=schemas.LocalizableDraftName(en="A fake category"),
    )
    async with db_session_maker() as session:
        await commands.create_dataset_category(session, to_create)
        assert await queries.get_dataset_category(session, to_create.id) is not None
        await commands.delete_dataset_category(session, to_create.id)
        assert await queries.get_dataset_category(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_domain_type(db, db_session_maker):
    to_create = schemas.DomainTypeCreate(
        id=schemas.DomainTypeId(uuid.UUID("28105b9e-03fb-40d2-96c3-6e449b1848ed")),
        name=schemas.LocalizableDraftName(en="A fake domain type"),
    )
    async with db_session_maker() as session:
        created = await commands.create_domain_type(session, to_create)
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name["en"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_domain_type(db, db_session_maker):
    to_create = schemas.DomainTypeCreate(
        id=schemas.DomainTypeId(uuid.UUID("d54bb541-a070-483d-8a5b-ac82f6f27a2b")),
        name=schemas.LocalizableDraftName(en="A fake domain type"),
    )
    async with db_session_maker() as session:
        await commands.create_domain_type(session, to_create)
        assert await queries.get_domain_type(session, to_create.id) is not None
        await commands.delete_domain_type(session, to_create.id)
        assert await queries.get_domain_type(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_workflow_stage(db, db_session_maker):
    to_create = schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("24d10a9f-8b30-4866-aa1b-5fe34a2f4ecf")),
        name=schemas.LocalizableDraftName(en="A fake workflow stage"),
    )
    async with db_session_maker() as session:
        created = await commands.create_workflow_stage(session, to_create)
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name["en"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_workflow_stage(db, db_session_maker):
    to_create = schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("adaf887f-27a9-40da-afe4-785a169c3edd")),
        name=schemas.LocalizableDraftName(en="A fake workflow stage"),
    )
    async with db_session_maker() as session:
        await commands.create_workflow_stage(session, to_create)
        assert await queries.get_workflow_stage(session, to_create.id) is not None
        await commands.delete_workflow_stage(session, to_create.id)
        assert await queries.get_workflow_stage(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_project(db, db_session_maker):
    to_create = schemas.ProjectCreate(
        id=schemas.ProjectId(uuid.UUID("5fe24752-5919-4a05-be46-aed53a6936db")),
        owner="fakeowner",
        name=schemas.LocalizableDraftName(en="A fake project", pt="Um projeto falso"),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake project",
            pt="Uma descrição para o projeto falso",
        ),
        root_path="/fake-path/to/fake-project/",
    )
    async with db_session_maker() as session:
        created = await commands.create_project(session, to_create)
        assert created.id == to_create.id
        assert created.owner == to_create.owner
        assert created.slug == "a-fake-project"
        assert created.name["en"] == to_create.name["en"]
        assert created.name["pt"] == to_create.name["pt"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_project(db, db_session_maker):
    to_create = schemas.ProjectCreate(
        id=schemas.ProjectId(uuid.UUID("0637d5d9-6381-4ba8-b9ec-89750baa93a4")),
        owner="fakeowner",
        name=schemas.LocalizableDraftName(en="A fake project", pt="Um projeto falso"),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake project",
            pt="Uma descrição para o projeto falso",
        ),
        root_path="/fake-path/to/fake-project/",
    )
    async with db_session_maker() as session:
        await commands.create_project(session, to_create)
        assert await queries.get_project(session, to_create.id) is not None
        await commands.delete_project(session, to_create.id)
        assert await queries.get_project(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_survey_mission(db, db_session_maker, sample_projects):
    to_create = schemas.SurveyMissionCreate(
        id=schemas.SurveyMissionId(uuid.UUID("1aad09c3-d606-445e-9216-d9620586c332")),
        project_id=schemas.ProjectId(sample_projects[0].id),
        owner=schemas.UserId("fakeowner"),
        name=schemas.LocalizableDraftName(
            en="A fake survey mission", pt="Uma missão falsa"
        ),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake survey mission",
            pt="Uma descrição para a missão falsa",
        ),
        relative_path="fake-mission",
    )
    async with db_session_maker() as session:
        created = await commands.create_survey_mission(session, to_create)
        assert created.id == to_create.id
        assert created.owner == to_create.owner
        assert created.slug == "a-fake-survey-mission"
        assert created.name["en"] == to_create.name["en"]
        assert created.name["pt"] == to_create.name["pt"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_survey_mission(db, db_session_maker, sample_projects):
    to_create = schemas.SurveyMissionCreate(
        id=schemas.SurveyMissionId(uuid.UUID("449a96e4-9b3b-41ad-a08b-75d31332b846")),
        project_id=schemas.ProjectId(sample_projects[0].id),
        owner=schemas.UserId("fakeowner"),
        name=schemas.LocalizableDraftName(
            en="A fake survey mission", pt="Uma missão falsa"
        ),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake survey mission",
            pt="Uma descrição para a missão falsa",
        ),
        relative_path="fake-mission",
    )
    async with db_session_maker() as session:
        await commands.create_survey_mission(session, to_create)
        assert await queries.get_survey_mission(session, to_create.id) is not None
        await commands.delete_survey_mission(session, to_create.id)
        assert await queries.get_survey_mission(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_survey_related_record(
    db,
    db_session_maker,
    sample_survey_missions,
    bootstrap_dataset_categories,
    bootstrap_domain_types,
    bootstrap_workflow_stages,
):
    dataset_category = [
        c for c in bootstrap_dataset_categories if c.name["en"] == "bathymetry"
    ][0]
    domain_type = [d for d in bootstrap_domain_types if d.name["en"] == "geophysical"][
        0
    ]
    workflow_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "raw data"
    ][0]
    to_create = schemas.SurveyRelatedRecordCreate(
        id=schemas.SurveyRelatedRecordId(
            uuid.UUID("cabe6a5f-d81c-496c-80cc-c3505b9121c2")
        ),
        survey_mission_id=schemas.SurveyMissionId(sample_survey_missions[0].id),
        owner=schemas.UserId("fakeowner"),
        name=schemas.LocalizableDraftName(
            en="A fake survey-related record", pt="Um registo falso"
        ),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake survey-related record",
            pt="Uma descrição para o registo falso",
        ),
        dataset_category_id=schemas.DatasetCategoryId(dataset_category.id),
        domain_type_id=schemas.DomainTypeId(domain_type.id),
        workflow_stage_id=schemas.WorkflowStageId(workflow_stage.id),
        relative_path="fake-record",
        assets=[
            schemas.RecordAssetCreate(
                id=schemas.RecordAssetId(
                    uuid.UUID("3cf81de8-60f3-44df-89f4-6f674a7fb94f")
                ),
                name=schemas.LocalizableDraftName(
                    en="first asset",
                    pt="primeiro registo",
                ),
                description=schemas.LocalizableDraftDescription(
                    en="description for first asset",
                    pt="descrição para o primeiro recurso",
                ),
                relative_path="asset1",
            ),
            schemas.RecordAssetCreate(
                id=schemas.RecordAssetId(
                    uuid.UUID("85ded7b6-a794-4746-b450-c3bdfb07e5c0")
                ),
                name=schemas.LocalizableDraftName(
                    en="second asset",
                    pt="segundo registo",
                ),
                description=schemas.LocalizableDraftDescription(
                    en="description for second asset",
                    pt="descrição para o segundo recurso",
                ),
                relative_path="asset2",
            ),
        ],
    )
    async with db_session_maker() as session:
        created = await commands.create_survey_related_record(session, to_create)
        assert created.id == to_create.id
        assert created.owner == to_create.owner
        assert created.slug == "a-fake-survey-related-record"
        assert created.name["en"] == to_create.name["en"]
        assert created.name["pt"] == to_create.name["pt"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_survey_related_record(
    db,
    db_session_maker,
    sample_survey_missions,
    bootstrap_dataset_categories,
    bootstrap_domain_types,
    bootstrap_workflow_stages,
):
    dataset_category = [
        c for c in bootstrap_dataset_categories if c.name["en"] == "bathymetry"
    ][0]
    domain_type = [d for d in bootstrap_domain_types if d.name["en"] == "geophysical"][
        0
    ]
    workflow_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "raw data"
    ][0]
    to_create = schemas.SurveyRelatedRecordCreate(
        id=schemas.SurveyRelatedRecordId(
            uuid.UUID("d0f6cb56-e942-4fd7-a0a9-083c3069d698")
        ),
        survey_mission_id=schemas.SurveyMissionId(sample_survey_missions[0].id),
        owner=schemas.UserId("fakeowner"),
        name=schemas.LocalizableDraftName(
            en="A fake survey-related record", pt="Um registo falso"
        ),
        description=schemas.LocalizableDraftDescription(
            en="A description for fake survey-related record",
            pt="Uma descrição para o registo falso",
        ),
        dataset_category_id=schemas.DatasetCategoryId(dataset_category.id),
        domain_type_id=schemas.DomainTypeId(domain_type.id),
        workflow_stage_id=schemas.WorkflowStageId(workflow_stage.id),
        relative_path="fake-record",
    )
    async with db_session_maker() as session:
        await commands.create_survey_related_record(session, to_create)
        assert (
            await queries.get_survey_related_record(session, to_create.id) is not None
        )
        await commands.delete_survey_related_record(session, to_create.id)
        assert await queries.get_survey_related_record(session, to_create.id) is None
