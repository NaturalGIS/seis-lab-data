import pydantic

from ..constants import ProcessingStatus

from .identifiers import (
    ProjectId,
    RequestId,
    SurveyRelatedRecordId,
    SurveyMissionId,
)


class ProjectUpdatedMessage(pydantic.BaseModel):
    project_id: ProjectId


class ProjectEvent(pydantic.BaseModel):
    project_id: ProjectId
    event: str
    message: str | None = None


class SurveyMissionUpdatedMessage(pydantic.BaseModel):
    survey_mission_id: SurveyMissionId


class SurveyMissionEvent(pydantic.BaseModel):
    survey_mission_id: SurveyMissionId
    event: str
    message: str | None = None


class SurveyRelatedRecordUpdatedMessage(pydantic.BaseModel):
    survey_related_record_id: SurveyRelatedRecordId


class SurveyRelatedRecordEvent(pydantic.BaseModel):
    survey_related_record_id: SurveyRelatedRecordId
    event: str
    message: str | None = None


class ProcessingMessage(pydantic.BaseModel):
    request_id: RequestId
    status: ProcessingStatus
    message: str
