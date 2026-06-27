import datetime as dt
import dataclasses
from functools import partial
from typing import TypeAlias

from .. import constants
from . import identifiers


get_utc_now = partial(dt.datetime.now, tz=dt.timezone.utc)


@dataclasses.dataclass(frozen=True, kw_only=True)
class _EventBase:
    initiator: str
    timestamp: dt.datetime = dataclasses.field(default_factory=get_utc_now)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceModificationEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    modification: constants.ResourceModification
    succeeded: bool
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceStatusChangedEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str | None
    succeeded: bool
    new_status: str | None
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiscoveryEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.DiscoveryStage
    succeeded: bool
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ValidationEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.ValidationStage
    succeeded: bool
    is_valid: bool
    details: str | None = None


SeisLabDataEvent: TypeAlias = (
    ResourceModificationEvent
    | ResourceStatusChangedEvent
    | DiscoveryEvent
    | ValidationEvent
)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationCreatedEvent(_EventBase):
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationNotCreatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationUpdatedEvent(_EventBase):
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationNotUpdatedEvent(_EventBase):
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationDeletedEvent(_EventBase):
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class AssetDiscoveryConfigurationNotDeletedEvent(_EventBase):
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId
    request_id: identifiers.RequestId | None = None
    details: str


# Project events


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectCreatedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectNotCreatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectUpdatedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectNotUpdatedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectDeletedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectNotDeletedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectStatusChangedEvent(_EventBase):
    project_id: identifiers.ProjectId
    old_status: constants.ProjectStatus
    new_status: constants.ProjectStatus


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectStatusNotChangedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    project_id: identifiers.ProjectId
    details: str


# this is emitted when the validation process errors out
@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectNotValidatedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectValidatedEvent(_EventBase):
    project_id: identifiers.ProjectId
    is_valid: bool
    details: list[dict[str, str]]


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectDiscoverySucceededEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectDiscoveryFailedEvent(_EventBase):
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId | None = None
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProjectDiscoveryProgressEvent(_EventBase):
    project_id: identifiers.ProjectId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionCreatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    project_id: identifiers.ProjectId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionNotCreatedEvent(_EventBase):
    request_id: identifiers.RequestId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionUpdatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionNotUpdatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionDeletedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    project_id: identifiers.ProjectId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionNotDeletedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionStatusChangedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    old_status: constants.SurveyMissionStatus
    new_status: constants.SurveyMissionStatus


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionStatusNotChangedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionValidatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    is_valid: bool


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionNotValidatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    survey_mission_id: identifiers.SurveyMissionId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyMissionDiscoveryProgressEvent(_EventBase):
    survey_mission_id: identifiers.SurveyMissionId
    project_id: identifiers.ProjectId
    details: str


# Survey-related record events


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordCreatedEvent(_EventBase):
    record_id: identifiers.SurveyRelatedRecordId
    survey_mission_id: identifiers.SurveyMissionId
    project_id: identifiers.ProjectId
    request_id: identifiers.RequestId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordNotCreatedEvent(_EventBase):
    request_id: identifiers.RequestId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordUpdatedEvent(_EventBase):
    record_id: identifiers.SurveyRelatedRecordId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordDeletedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    survey_mission_id: identifiers.SurveyMissionId
    project_id: identifiers.ProjectId


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordNotDeletedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordStatusChangedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    old_status: constants.SurveyRelatedRecordStatus
    new_status: constants.SurveyRelatedRecordStatus


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordStatusNotChangedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    details: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordValidatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    is_valid: bool


@dataclasses.dataclass(frozen=True, kw_only=True)
class SurveyRelatedRecordNotValidatedEvent(_EventBase):
    request_id: identifiers.RequestId | None = None
    record_id: identifiers.SurveyRelatedRecordId
    details: str


# Reference data events


@dataclasses.dataclass(frozen=True, kw_only=True)
class DatasetCategoryCreatedEvent(_EventBase):
    category_id: identifiers.DatasetCategoryId


@dataclasses.dataclass(frozen=True, kw_only=True)
class DatasetCategoryDeletedEvent(_EventBase):
    category_id: identifiers.DatasetCategoryId


@dataclasses.dataclass(frozen=True, kw_only=True)
class WorkflowStageCreatedEvent(_EventBase):
    stage_id: identifiers.WorkflowStageId


@dataclasses.dataclass(frozen=True, kw_only=True)
class WorkflowStageDeletedEvent(_EventBase):
    stage_id: identifiers.WorkflowStageId


OldSeisLabDataEvent: TypeAlias = (
    AssetDiscoveryConfigurationCreatedEvent
    | AssetDiscoveryConfigurationNotCreatedEvent
    | AssetDiscoveryConfigurationUpdatedEvent
    | AssetDiscoveryConfigurationNotUpdatedEvent
    | AssetDiscoveryConfigurationDeletedEvent
    | AssetDiscoveryConfigurationNotDeletedEvent
    | ProjectCreatedEvent
    | ProjectNotCreatedEvent
    | ProjectUpdatedEvent
    | ProjectNotUpdatedEvent
    | ProjectDeletedEvent
    | ProjectNotDeletedEvent
    | ProjectStatusChangedEvent
    | ProjectStatusNotChangedEvent
    | ProjectValidatedEvent
    | ProjectNotValidatedEvent
    | ProjectDiscoverySucceededEvent
    | ProjectDiscoveryFailedEvent
    | ProjectDiscoveryProgressEvent
    | SurveyMissionCreatedEvent
    | SurveyMissionNotCreatedEvent
    | SurveyMissionUpdatedEvent
    | SurveyMissionNotUpdatedEvent
    | SurveyMissionDeletedEvent
    | SurveyMissionNotDeletedEvent
    | SurveyMissionStatusChangedEvent
    | SurveyMissionStatusNotChangedEvent
    | SurveyMissionValidatedEvent
    | SurveyMissionNotValidatedEvent
    | SurveyMissionDiscoveryProgressEvent
    | SurveyRelatedRecordCreatedEvent
    | SurveyRelatedRecordNotCreatedEvent
    | SurveyRelatedRecordUpdatedEvent
    | SurveyRelatedRecordDeletedEvent
    | SurveyRelatedRecordNotDeletedEvent
    | SurveyRelatedRecordStatusChangedEvent
    | SurveyRelatedRecordStatusNotChangedEvent
    | SurveyRelatedRecordValidatedEvent
    | SurveyRelatedRecordNotValidatedEvent
    | DatasetCategoryCreatedEvent
    | DatasetCategoryDeletedEvent
    | WorkflowStageCreatedEvent
    | WorkflowStageDeletedEvent
)
