from typing import (
    Annotated,
    Literal,
    TypeAlias,
)

from . import identifiers
from .. import constants

import pydantic


class ProjectDiscoverySuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_discovery_successful"] = "project_discovery_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str | None = None


class ProjectDiscoveryFailedMessage(pydantic.BaseModel):
    type: Literal["project_discovery_failed"] = "project_discovery_failed"
    request_id: identifiers.RequestId | None = None
    project_id: identifiers.ProjectId
    details: str


class ProjectCreatedMessage(pydantic.BaseModel):
    type: Literal["project_created"] = "project_created"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


class ProjectNotCreatedMessage(pydantic.BaseModel):
    type: Literal["project_not_created"] = "project_not_created"
    request_id: identifiers.RequestId | None = None
    details: str


class ProjectUpdatedMessage(pydantic.BaseModel):
    type: Literal["project_updated"] = "project_updated"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


class ProjectNotUpdatedMessage(pydantic.BaseModel):
    type: Literal["project_not_updated"] = "project_updated"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


class ProjectDeletedMessage(pydantic.BaseModel):
    type: Literal["project_deleted"] = "project_deleted"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


class ProjectNotDeletedMessage(pydantic.BaseModel):
    type: Literal["project_not_deleted"] = "project_not_deleted"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


class ProjectStatusChangedMessage(pydantic.BaseModel):
    type: Literal["project_status_changed"] = "project_status_changed"
    project_id: identifiers.ProjectId
    new_status: constants.ProjectStatus


class ProjectValidatedMessage(pydantic.BaseModel):
    type: Literal["project_validated"] = "project_validated"
    project_id: identifiers.ProjectId
    is_valid: bool


class ProjectNotValidatedMessage(pydantic.BaseModel):
    type: Literal["project_not_validated"] = "project_not_validated"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


class ProjectDiscoveryProgressMessage(pydantic.BaseModel):
    type: Literal["project_discovery_progress"] = "project_discovery_progress"
    project_id: identifiers.ProjectId
    details: str


# Survey mission broadcast messages


class SurveyMissionCreatedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_created"] = "survey_mission_created"
    survey_mission_id: identifiers.SurveyMissionId
    request_id: identifiers.RequestId | None = None


class SurveyMissionUpdatedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_updated"] = "survey_mission_updated"
    survey_mission_id: identifiers.SurveyMissionId
    request_id: identifiers.RequestId | None = None


class SurveyMissionDeletedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_deleted"] = "survey_mission_deleted"
    survey_mission_id: identifiers.SurveyMissionId
    request_id: identifiers.RequestId | None = None


class SurveyMissionStatusChangedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_status_changed"] = "survey_mission_status_changed"
    survey_mission_id: identifiers.SurveyMissionId
    new_status: constants.SurveyMissionStatus


class SurveyMissionValidatedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_validated"] = "survey_mission_validated"
    survey_mission_id: identifiers.SurveyMissionId
    is_valid: bool


class SurveyMissionDiscoveryProgressMessage(pydantic.BaseModel):
    type: Literal["survey_mission_discovery_progress"] = (
        "survey_mission_discovery_progress"
    )
    survey_mission_id: identifiers.SurveyMissionId
    details: str


# Survey related record broadcast messages


class SurveyRelatedRecordCreatedMessage(pydantic.BaseModel):
    type: Literal["survey_related_record_created"] = "survey_related_record_created"
    record_id: identifiers.SurveyRelatedRecordId
    survey_mission_id: identifiers.SurveyMissionId
    request_id: identifiers.RequestId | None = None


class SurveyRelatedRecordUpdatedMessage(pydantic.BaseModel):
    type: Literal["survey_related_record_updated"] = "survey_related_record_updated"
    record_id: identifiers.SurveyRelatedRecordId


class SurveyRelatedRecordDeletedMessage(pydantic.BaseModel):
    type: Literal["survey_related_record_deleted"] = "survey_related_record_deleted"
    record_id: identifiers.SurveyRelatedRecordId


class SurveyRelatedRecordStatusChangedMessage(pydantic.BaseModel):
    type: Literal["survey_related_record_status_changed"] = (
        "survey_related_record_status_changed"
    )
    record_id: identifiers.SurveyRelatedRecordId
    new_status: constants.SurveyRelatedRecordStatus


class SurveyRelatedRecordValidatedMessage(pydantic.BaseModel):
    type: Literal["survey_related_record_validated"] = "survey_related_record_validated"
    record_id: identifiers.SurveyRelatedRecordId
    is_valid: bool


SldPubSubMessage: TypeAlias = Annotated[
    ProjectDiscoverySuccessfulMessage
    | ProjectDiscoveryFailedMessage
    | ProjectCreatedMessage
    | ProjectNotCreatedMessage
    | ProjectUpdatedMessage
    | ProjectDeletedMessage
    | ProjectNotDeletedMessage
    | ProjectStatusChangedMessage
    | ProjectValidatedMessage
    | ProjectNotValidatedMessage
    | ProjectDiscoveryProgressMessage
    | SurveyMissionCreatedMessage
    | SurveyMissionUpdatedMessage
    | SurveyMissionDeletedMessage
    | SurveyMissionStatusChangedMessage
    | SurveyMissionValidatedMessage
    | SurveyMissionDiscoveryProgressMessage
    | SurveyRelatedRecordCreatedMessage
    | SurveyRelatedRecordUpdatedMessage
    | SurveyRelatedRecordDeletedMessage
    | SurveyRelatedRecordStatusChangedMessage
    | SurveyRelatedRecordValidatedMessage,
    pydantic.Field(discriminator="type"),
]
