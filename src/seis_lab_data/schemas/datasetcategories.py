import logging
from typing import Annotated

import pydantic

from ..db import models
from . import (
    common,
    identifiers,
)

logger = logging.getLogger(__name__)


class DatasetCategoryCreate(pydantic.BaseModel):
    id: identifiers.DatasetCategoryId
    name: common.DraftName


class DatasetCategoryUpdate(pydantic.BaseModel):
    name: common.DraftName | None = None


class DatasetCategoryReadListItem(pydantic.BaseModel):
    id: Annotated[
        identifiers.DatasetCategoryId, pydantic.PlainSerializer(common.serialize_id)
    ]
    name: common.DraftName

    @classmethod
    def from_db_instance(
        cls,
        instance: models.DatasetCategory,
    ) -> "DatasetCategoryReadListItem":
        return cls.model_validate(instance, from_attributes=True)
