import logging
from typing import Annotated

import pydantic

from ..db import models
from . import (
    common,
    identifiers,
)

logger = logging.getLogger(__name__)


class WorkflowStageCreate(pydantic.BaseModel):
    id: identifiers.WorkflowStageId
    name: common.LocalizableDraftName


class WorkflowStageUpdate(pydantic.BaseModel):
    name: common.LocalizableDraftName | None = None


class WorkflowStageReadListItem(pydantic.BaseModel):
    id: Annotated[
        identifiers.WorkflowStageId, pydantic.PlainSerializer(common.serialize_id)
    ]
    name: common.LocalizableDraftName

    @classmethod
    def from_db_instance(
        cls,
        instance: models.WorkflowStage,
    ) -> "WorkflowStageReadListItem":
        return cls.model_validate(instance, from_attributes=True)
