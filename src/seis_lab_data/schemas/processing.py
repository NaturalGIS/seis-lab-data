import pydantic

from ..constants import ProcessingStatus
from .common import (
    ProjectId,
    RequestId,
)

from . import events


class ProjectUpdatedMessage(pydantic.BaseModel):
    project_id: ProjectId


class ProjectEvent(pydantic.BaseModel):
    project_id: ProjectId
    event: events.EventType
    message: str | None = None


class ProcessingMessage(pydantic.BaseModel):
    request_id: RequestId
    status: ProcessingStatus
    message: str
