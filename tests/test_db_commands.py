import uuid

import pytest

from seis_lab_data.db.commands import (
    projects as project_commands,
    surveymissions as mission_commands,
    surveyrelatedrecords as record_commands,
)
from seis_lab_data.db.queries import (
    projects as project_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
    datasetcategories as category_queries,
    workflowstages as stage_queries,
)
from seis_lab_data.schemas import (
    common as common_schemas,
    identifiers,
    projects as project_schemas,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_dataset_category(db, db_session_maker):
    to_create = record_schemas.DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("303cad6d-2e0e-447e-85e1-c284c1c882a7")
        ),
        name=common_schemas.LocalizableDraftName(en="A fake category"),
    )
    async with db_session_maker() as session:
        created = await record_commands.create_dataset_category(session, to_create)
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name.en


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_dataset_category(db, db_session_maker):
    to_create = record_schemas.DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("26b06713-dce1-4304-bf50-fec5c3f5efe6")
        ),
        name=common_schemas.LocalizableDraftName(en="A fake category"),
    )
    async with db_session_maker() as session:
        await record_commands.create_dataset_category(session, to_create)
        assert (
            await category_queries.get_dataset_category(session, to_create.id)
            is not None
        )
        await record_commands.delete_dataset_category(session, to_create.id)
        assert (
            await category_queries.get_dataset_category(session, to_create.id) is None
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_workflow_stage(db, db_session_maker):
    to_create = record_schemas.WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("24d10a9f-8b30-4866-aa1b-5fe34a2f4ecf")
        ),
        name=common_schemas.LocalizableDraftName(en="A fake workflow stage"),
    )
    async with db_session_maker() as session:
        created = await record_commands.create_workflow_stage(session, to_create)
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name.en


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_workflow_stage(db, db_session_maker):
    to_create = record_schemas.WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("adaf887f-27a9-40da-afe4-785a169c3edd")
        ),
        name=common_schemas.LocalizableDraftName(en="A fake workflow stage"),
    )
    async with db_session_maker() as session:
        await record_commands.create_workflow_stage(session, to_create)
        assert await stage_queries.get_workflow_stage(session, to_create.id) is not None
        await record_commands.delete_workflow_stage(session, to_create.id)
        assert await stage_queries.get_workflow_stage(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_project(db, db_session_maker, admin_user):
    to_create = project_schemas.ProjectCreate(
        id=identifiers.ProjectId(uuid.UUID("5fe24752-5919-4a05-be46-aed53a6936db")),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake project", pt="Um projeto falso"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake project",
            pt="Uma descrição para o projeto falso",
        ),
        root_path="/fake-path/to/fake-project/",
    )
    async with db_session_maker() as session:
        created = await project_commands.create_project(session, to_create)
        assert created.id == to_create.id
        assert created.owner_id == to_create.owner_id
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name.en
        assert created.name["pt"] == to_create.name.pt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_project(db, db_session_maker, admin_user):
    to_create = project_schemas.ProjectCreate(
        id=identifiers.ProjectId(uuid.UUID("0637d5d9-6381-4ba8-b9ec-89750baa93a4")),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake project", pt="Um projeto falso"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake project",
            pt="Uma descrição para o projeto falso",
        ),
        root_path="/fake-path/to/fake-project/",
    )
    async with db_session_maker() as session:
        await project_commands.create_project(session, to_create)
        assert await project_queries.get_project(session, to_create.id) is not None
        await project_commands.delete_project(session, to_create.id)
        assert await project_queries.get_project(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_survey_mission(db, db_session_maker, sample_projects, admin_user):
    to_create = mission_schemas.SurveyMissionCreate(
        id=identifiers.SurveyMissionId(
            uuid.UUID("1aad09c3-d606-445e-9216-d9620586c332")
        ),
        project_id=identifiers.ProjectId(sample_projects[0].id),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake survey mission", pt="Uma missão falsa"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake survey mission",
            pt="Uma descrição para a missão falsa",
        ),
        relative_path="fake-mission",
    )
    async with db_session_maker() as session:
        created = await mission_commands.create_survey_mission(session, to_create)
        assert created.id == to_create.id
        assert created.owner_id == to_create.owner_id
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name.en
        assert created.name["pt"] == to_create.name.pt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_survey_mission(db, db_session_maker, sample_projects, admin_user):
    to_create = mission_schemas.SurveyMissionCreate(
        id=identifiers.SurveyMissionId(
            uuid.UUID("449a96e4-9b3b-41ad-a08b-75d31332b846")
        ),
        project_id=identifiers.ProjectId(sample_projects[0].id),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake survey mission", pt="Uma missão falsa"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake survey mission",
            pt="Uma descrição para a missão falsa",
        ),
        relative_path="fake-mission",
    )
    async with db_session_maker() as session:
        await mission_commands.create_survey_mission(session, to_create)
        assert (
            await mission_queries.get_survey_mission(session, to_create.id) is not None
        )
        await mission_commands.delete_survey_mission(session, to_create.id)
        assert await mission_queries.get_survey_mission(session, to_create.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_survey_related_record(
    db,
    db_session_maker,
    sample_survey_missions,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
    admin_user,
):
    dataset_category = [
        c for c in bootstrap_dataset_categories if c.name["en"] == "bathymetry"
    ][0]
    workflow_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "raw data"
    ][0]
    to_create = record_schemas.SurveyRelatedRecordCreate(
        id=identifiers.SurveyRelatedRecordId(
            uuid.UUID("cabe6a5f-d81c-496c-80cc-c3505b9121c2")
        ),
        survey_mission_id=identifiers.SurveyMissionId(sample_survey_missions[0].id),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake survey-related record", pt="Um registo falso"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake survey-related record",
            pt="Uma descrição para o registo falso",
        ),
        dataset_category_id=identifiers.DatasetCategoryId(dataset_category.id),
        workflow_stage_id=identifiers.WorkflowStageId(workflow_stage.id),
        relative_path="fake-record",
        assets=[
            record_schemas.RecordAssetCreate(
                id=identifiers.RecordAssetId(
                    uuid.UUID("3cf81de8-60f3-44df-89f4-6f674a7fb94f")
                ),
                name=common_schemas.LocalizableDraftName(
                    en="first asset",
                    pt="primeiro registo",
                ),
                description=common_schemas.LocalizableDraftDescription(
                    en="description for first asset",
                    pt="descrição para o primeiro recurso",
                ),
                relative_path="asset1",
            ),
            record_schemas.RecordAssetCreate(
                id=identifiers.RecordAssetId(
                    uuid.UUID("85ded7b6-a794-4746-b450-c3bdfb07e5c0")
                ),
                name=common_schemas.LocalizableDraftName(
                    en="second asset",
                    pt="segundo registo",
                ),
                description=common_schemas.LocalizableDraftDescription(
                    en="description for second asset",
                    pt="descrição para o segundo recurso",
                ),
                relative_path="asset2",
            ),
        ],
    )
    async with db_session_maker() as session:
        created = await record_commands.create_survey_related_record(session, to_create)
        assert created.id == to_create.id
        assert created.owner_id == to_create.owner_id
        assert created.id == to_create.id
        assert created.name["en"] == to_create.name.en
        assert created.name["pt"] == to_create.name.pt


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_survey_related_record(
    db,
    db_session_maker,
    sample_survey_missions,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
    admin_user,
):
    dataset_category = [
        c for c in bootstrap_dataset_categories if c.name["en"] == "bathymetry"
    ][0]
    workflow_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "raw data"
    ][0]
    to_create = record_schemas.SurveyRelatedRecordCreate(
        id=identifiers.SurveyRelatedRecordId(
            uuid.UUID("d0f6cb56-e942-4fd7-a0a9-083c3069d698")
        ),
        survey_mission_id=identifiers.SurveyMissionId(sample_survey_missions[0].id),
        owner_id=admin_user.id,
        name=common_schemas.LocalizableDraftName(
            en="A fake survey-related record", pt="Um registo falso"
        ),
        description=common_schemas.LocalizableDraftDescription(
            en="A description for fake survey-related record",
            pt="Uma descrição para o registo falso",
        ),
        dataset_category_id=identifiers.DatasetCategoryId(dataset_category.id),
        workflow_stage_id=identifiers.WorkflowStageId(workflow_stage.id),
        relative_path="fake-record",
    )
    async with db_session_maker() as session:
        await record_commands.create_survey_related_record(session, to_create)
        assert (
            await record_queries.get_survey_related_record(session, to_create.id)
            is not None
        )
        await record_commands.delete_survey_related_record(session, to_create.id)
        assert (
            await record_queries.get_survey_related_record(session, to_create.id)
            is None
        )
