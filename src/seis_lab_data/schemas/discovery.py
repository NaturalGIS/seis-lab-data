from typing import Annotated

import pydantic

from .. import constants
from ..db import models
from . import (
    common,
    identifiers,
    datasetcategories as category_schemas,
    workflowstages as stage_schemas,
)


class NewAssetDiscoveryConfiguration(pydantic.BaseModel):
    identifier: identifiers.AssetDiscoveryConfId
    relative_path_regexp: str
    workflow_stage: str
    category: str


class AssetDiscoveryConfigurationCreate(pydantic.BaseModel):
    id: identifiers.AssetDiscoveryConfId
    name: Annotated[
        str, pydantic.Field(min_length=1, max_length=constants.NAME_MAX_LENGTH)
    ]
    relative_path_regexp: str
    media_type: str
    workflow_stage_id: identifiers.WorkflowStageId
    dataset_category_id: identifiers.DatasetCategoryId


class AssetDiscoveryConfigurationUpdate(pydantic.BaseModel):
    name: str | None = None
    relative_path_regexp: str | None = None
    media_type: str | None = None
    workflow_stage_id: identifiers.WorkflowStageId | None = None
    dataset_category_id: identifiers.DatasetCategoryId | None = None


class AssetDiscoveryConfigurationReadListItem(pydantic.BaseModel):
    id: Annotated[
        identifiers.AssetDiscoveryConfId, pydantic.PlainSerializer(common.serialize_id)
    ]
    name: str
    relative_path_regexp: str
    media_type: str
    workflow_stage: stage_schemas.WorkflowStageReadListItem
    dataset_category: category_schemas.DatasetCategoryReadListItem

    @classmethod
    def from_db_instance(
        cls, instance: models.AssetDiscoveryConfiguration
    ) -> "AssetDiscoveryConfigurationReadListItem":
        return cls.model_validate(instance, from_attributes=True)


class AssetDiscoveryConfigurationReadDetail(AssetDiscoveryConfigurationReadListItem):
    @classmethod
    def from_db_instance(
        cls, instance: models.AssetDiscoveryConfiguration
    ) -> "AssetDiscoveryConfigurationReadDetail":
        return cls.model_validate(instance, from_attributes=True)
