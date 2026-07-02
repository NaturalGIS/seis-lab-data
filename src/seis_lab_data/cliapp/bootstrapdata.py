import uuid

from ..schemas.common import (
    LocalizableDraftName,
)
from ..schemas import identifiers
from ..schemas.datasetcategories import DatasetCategoryCreate
from ..schemas.discovery import AssetDiscoveryConfigurationCreate
from ..schemas.workflowstages import WorkflowStageCreate

DATASET_CATEGORIES_TO_CREATE: dict[str, DatasetCategoryCreate] = {
    "bathymetry": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("1ad54ca0-a28b-46c0-9776-3c9b7f3bc990")
        ),
        name=LocalizableDraftName(en="bathymetry", pt="batimetria"),
    ),
    "backscatter": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("3002d462-3f2e-4957-a56e-97175f91883a")
        ),
        name=LocalizableDraftName(en="backscatter", pt="backscatter"),
    ),
    "seismic": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("53ec7259-5fbe-48d7-9d1b-508225add0a0")
        ),
        name=LocalizableDraftName(en="seismic", pt="sismíca"),
    ),
    "magnetometer/gradiometer": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("333073eb-adc9-4ac7-b822-44f4df5575a3")
        ),
        name=LocalizableDraftName(
            en="magnetometer/gradiometer", pt="magnetómetro/gradiómetro"
        ),
    ),
    "superficial sediment samples": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("4b17a645-dc10-488c-ba7d-47ff052efdf8")
        ),
        name=LocalizableDraftName(
            en="superficial sediment samples", pt="amostras sedimento superficial"
        ),
    ),
    "cores": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("fd68accf-057e-4813-b47a-aa4df3741c45")
        ),
        name=LocalizableDraftName(
            en="cores",
            pt="núcleos",
        ),
    ),
    "CPT tests": DatasetCategoryCreate(
        id=identifiers.DatasetCategoryId(
            uuid.UUID("43507846-a6cf-4e54-bd80-9ef5be334cf0")
        ),
        name=LocalizableDraftName(
            en="CPT tests",
            pt="testes CPT",
        ),
    ),
}

WORKFLOW_STAGES_TO_CREATE: dict[str, WorkflowStageCreate] = {
    "raw data": WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("ac51aa07-90e9-43d4-83b9-d079482a001e")
        ),
        name=LocalizableDraftName(
            en="raw data",
            pt="dados brutos",
        ),
    ),
    "quality control data": WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("6dc042b3-16f9-4a9a-a30a-ac9201b4eb1d")
        ),
        name=LocalizableDraftName(
            en="quality control data",
            pt="dados controlo de qualidade",
        ),
    ),
    "processed data": WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("372ac9ed-c7b9-4be3-9030-30149f0b4295")
        ),
        name=LocalizableDraftName(
            en="processed data",
            pt="dados processados",
        ),
    ),
    "interpreted data": WorkflowStageCreate(
        id=identifiers.WorkflowStageId(
            uuid.UUID("342fb236-6622-495e-ae6c-fd90f5cf0d16")
        ),
        name=LocalizableDraftName(
            en="interpreted data",
            pt="dados interpretados",
        ),
    ),
}

ASSET_DISCOVERY_CONFIGURATIONS_TO_CREATE: dict[
    str, AssetDiscoveryConfigurationCreate
] = {
    "raw_kmall": AssetDiscoveryConfigurationCreate(
        id=identifiers.AssetDiscoveryConfId(
            uuid.UUID("3128b241-73a0-4f6f-88d0-75bb9424de25")
        ),
        name="raw_kmall",
        relative_path_regexp="s06-mbes/s02-raw-data/.*\\.kmall",
        workflow_stage_id=WORKFLOW_STAGES_TO_CREATE["raw data"].id,
        dataset_category_id=DATASET_CATEGORIES_TO_CREATE["bathymetry"].id,
    ),
    # "raw_uhrs_segy": AssetDiscoveryConfigurationCreate(
    #     id=identifiers.AssetDiscoveryConfId(uuid.UUID("57e5866c-b5d7-4e16-9e4c-411d7b1196bc")),
    #     name="raw_uhrs_segy",
    #     relative_path_regexp="s13-uhrs/s02-raw-data/.*\\.segy",
    #     workflow_stage_id=WORKFLOW_STAGES_TO_CREATE["raw data"].id,
    #     dataset_category_id=DATASET_CATEGORIES_TO_CREATE["uhrs"].id,
    # )
}
