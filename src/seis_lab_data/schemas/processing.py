import pydantic

from ..constants import ProcessingStatus
from .common import (
    ProjectId,
    RequestId,
)


class ProjectUpdatedMessage(pydantic.BaseModel):
    project_id: ProjectId


class ProjectEvent(pydantic.BaseModel):
    project_id: ProjectId
    message: str


class ProcessingMessage(pydantic.BaseModel):
    request_id: RequestId
    status: ProcessingStatus
    message: str
