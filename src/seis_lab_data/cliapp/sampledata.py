import uuid

import pydantic

from .. import schemas
from ..db import models

_owner_id = schemas.UserId("fake-owner1")
_my_first_project_id = schemas.ProjectId(
    uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3")
)
_my_second_project_id = schemas.ProjectId(
    uuid.UUID("9a877fbe-da98-45ab-af70-711879c6fc01")
)

_my_first_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("cfe10cd8-5a5e-40e4-807b-7064f94a2edf")
)
_my_second_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("38d9ad16-6cf5-4c64-abfe-0915c6c22268")
)
_my_third_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("ebedf3e5-38a4-42ad-bb60-52b4eee6bd54")
)
_my_fourth_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("03a5f8c1-60ba-4309-a06a-e7b0c8851f20")
)
_my_fifth_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("51a44e56-42e7-4aab-a1c7-659436df99c1")
)


def get_projects_to_create() -> list[schemas.ProjectCreate]:
    return [
        schemas.ProjectCreate(
            id=_my_first_project_id,
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="My first project", pt="O meu primeiro projeto"
            ),
            description=schemas.LocalizableDraftDescription(
                en="A Fake description for my first project",
                pt="Uma descrição falsa para o meu primeiro projeto",
            ),
            root_path="/projects/first",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for link",
                        pt="Uma descrição falsa para o link",
                    ),
                ),
            ],
        ),
        schemas.ProjectCreate(
            id=_my_second_project_id,
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="My second project", pt="O meu segundo projeto"
            ),
            description=schemas.LocalizableDraftDescription(
                en="A fake description for my second project",
                pt="Uma descrição sintética para o meu segundo projeto",
            ),
            root_path="/projects/second",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for link",
                        pt="Uma descrição falsa para o link",
                    ),
                )
            ],
        ),
    ]


def get_survey_missions_to_create() -> list[schemas.SurveyMissionCreate]:
    return [
        schemas.SurveyMissionCreate(
            id=_my_first_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My first survey mission", pt="A minha primeira missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my first survey mission",
                pt="Esta é a descrição para a minha primeira missão",
            ),
            relative_path="mission1",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_second_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My second survey mission", pt="A minha segunda missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my second survey mission",
                pt="Esta é a descrição para a minha segunda missão",
            ),
            relative_path="mission2",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_third_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My third survey mission", pt="A minha terceira missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my third survey mission",
                pt="Esta é a descrição para a minha terceira missão",
            ),
            relative_path="mission3",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_fourth_survey_mission_id,
            owner=_owner_id,
            project_id=_my_second_project_id,
            name=schemas.LocalizableDraftName(
                en="My fourth survey mission", pt="A minha quarta missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my fourth survey mission",
                pt="Esta é a descrição para a minha quarta missão",
            ),
            relative_path="mission4",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_fifth_survey_mission_id,
            owner=_owner_id,
            project_id=_my_second_project_id,
            name=schemas.LocalizableDraftName(
                en="My fifth survey mission", pt="A minha quinta missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my fifth survey mission",
                pt="Esta é a descrição para a minha quinta missão",
            ),
            relative_path="mission5",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
    ]


def get_survey_related_records_to_create(
    dataset_categories: dict[str, models.DatasetCategory],
    domain_types: dict[str, models.DomainType],
    workflow_stages: dict[str, models.WorkflowStage],
) -> list[schemas.SurveyRelatedRecordCreate]:
    return [
        schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(
                uuid.UUID("f49d678b-f11a-4798-92dc-604883bc8bda")
            ),
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="First record",
                pt="Primeiro registo",
            ),
            description=schemas.LocalizableDraftDescription(
                en="Description for first record",
                pt="Descrição do primeiro registo",
            ),
            survey_mission_id=_my_first_survey_mission_id,
            dataset_category_id=schemas.DatasetCategoryId(
                dataset_categories["bathymetry"].id
            ),
            domain_type_id=schemas.DomainTypeId(domain_types["geophysical"].id),
            workflow_stage_id=schemas.WorkflowStageId(workflow_stages["raw data"].id),
            relative_path="first-record",
            links=[],
        ),
        schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(
                uuid.UUID("c51e0d11-c4c4-4b4f-8d04-2a115196ff04")
            ),
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="Second record",
                pt="Segundo registo",
            ),
            description=schemas.LocalizableDraftDescription(
                en="Description for second record",
                pt="Descrição do segundo registo",
            ),
            survey_mission_id=_my_second_survey_mission_id,
            dataset_category_id=schemas.DatasetCategoryId(
                dataset_categories["bathymetry"].id
            ),
            domain_type_id=schemas.DomainTypeId(domain_types["geophysical"].id),
            workflow_stage_id=schemas.WorkflowStageId(workflow_stages["raw data"].id),
            relative_path="second-record",
            links=[],
        ),
    ]
