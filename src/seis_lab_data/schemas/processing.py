import pydantic

from ..constants import ProcessingStatus
from .common import RequestId


class ProcessingMessage(pydantic.BaseModel):
    request_id: RequestId
    status: ProcessingStatus
    message: str
