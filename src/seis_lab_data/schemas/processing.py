import pydantic

from ..constants import ProcessingStatus
from .common import (
    ProjectId,
    SurveyMissionId,
    SurveyRelatedRecordId,
    RequestId,
)

from . import events


class ProjectUpdatedMessage(pydantic.BaseModel):
    project_id: ProjectId


class ProjectEvent(pydantic.BaseModel):
    project_id: ProjectId
    event: events.EventType
    message: str | None = None


class SurveyMissionUpdatedMessage(pydantic.BaseModel):
    survey_mission_id: SurveyMissionId


class SurveyMissionEvent(pydantic.BaseModel):
    survey_mission_id: SurveyMissionId
    event: events.EventType
    message: str | None = None


class SurveyRelatedRecordUpdatedMessage(pydantic.BaseModel):
    survey_related_record_id: SurveyRelatedRecordId


class SurveyRelatedRecordEvent(pydantic.BaseModel):
    survey_related_record_id: SurveyRelatedRecordId
    event: events.EventType
    message: str | None = None


class ProcessingMessage(pydantic.BaseModel):
    request_id: RequestId
    status: ProcessingStatus
    message: str
