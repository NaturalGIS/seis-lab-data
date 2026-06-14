from typing import (
    Annotated,
    Literal,
    TypeAlias,
)

from . import identifiers
from .. import constants

import pydantic


# CRUD request-scoped messages (include request_id for client correlation)


class ProjectCreationStartedMessage(pydantic.BaseModel):
    type: Literal["project_creation_started"] = "project_creation_started"
    request_id: identifiers.RequestId


class ProjectCreationSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_creation_successful"] = "project_creation_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectCreationFailedMessage(pydantic.BaseModel):
    type: Literal["project_creation_failed"] = "project_creation_failed"
    request_id: identifiers.RequestId
    details: str


class ProjectUpdateStartedMessage(pydantic.BaseModel):
    type: Literal["project_update_started"] = "project_update_started"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectUpdateSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_update_successful"] = "project_update_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectUpdateFailedMessage(pydantic.BaseModel):
    type: Literal["project_update_failed"] = "project_update_failed"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str


class ProjectDeletionStartedMessage(pydantic.BaseModel):
    type: Literal["project_deletion_started"] = "project_deletion_started"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectDeletionSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_deletion_successful"] = "project_deletion_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectDeletionFailedMessage(pydantic.BaseModel):
    type: Literal["project_deletion_failed"] = "project_deletion_failed"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str


class ProjectDiscoveryStartedMessage(pydantic.BaseModel):
    type: Literal["project_discovery_started"] = "project_discovery_started"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectDiscoverySuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_discovery_successful"] = "project_discovery_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str | None = None


class ProjectDiscoveryFailedMessage(pydantic.BaseModel):
    type: Literal["project_discovery_failed"] = "project_discovery_failed"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str


# Project broadcast messages (no request_id, delivered to all subscribers)


class ProjectCreatedMessage(pydantic.BaseModel):
    type: Literal["project_created"] = "project_created"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


class ProjectNotCreatedMessage(pydantic.BaseModel):
    type: Literal["project_not_created"] = "project_not_created"
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId
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


class ProjectStatusChangedMessage(pydantic.BaseModel):
    type: Literal["project_status_changed"] = "project_status_changed"
    project_id: identifiers.ProjectId
    new_status: constants.ProjectStatus


class ProjectValidatedMessage(pydantic.BaseModel):
    type: Literal["project_validated"] = "project_validated"
    project_id: identifiers.ProjectId
    is_valid: bool


class ProjectDiscoveryProgressMessage(pydantic.BaseModel):
    type: Literal["project_discovery_progress"] = "project_discovery_progress"
    project_id: identifiers.ProjectId
    details: str


# Survey mission broadcast messages


class SurveyMissionCreatedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_created"] = "survey_mission_created"
    survey_mission_id: identifiers.SurveyMissionId


class SurveyMissionUpdatedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_updated"] = "survey_mission_updated"
    survey_mission_id: identifiers.SurveyMissionId


class SurveyMissionDeletedMessage(pydantic.BaseModel):
    type: Literal["survey_mission_deleted"] = "survey_mission_deleted"
    survey_mission_id: identifiers.SurveyMissionId


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
    ProjectCreationStartedMessage
    | ProjectCreationFailedMessage
    | ProjectCreationSuccessfulMessage
    | ProjectUpdateStartedMessage
    | ProjectUpdateFailedMessage
    | ProjectUpdateSuccessfulMessage
    | ProjectDeletionStartedMessage
    | ProjectDeletionFailedMessage
    | ProjectDeletionSuccessfulMessage
    | ProjectDiscoveryStartedMessage
    | ProjectDiscoverySuccessfulMessage
    | ProjectDiscoveryFailedMessage
    | ProjectCreatedMessage
    | ProjectUpdatedMessage
    | ProjectDeletedMessage
    | ProjectStatusChangedMessage
    | ProjectValidatedMessage
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
