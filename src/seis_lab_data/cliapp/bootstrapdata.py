import uuid

from .. import schemas

DATASET_CATEGORIES_TO_CREATE: dict[str, schemas.DatasetCategoryCreate] = {
    "bathymetry": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("1ad54ca0-a28b-46c0-9776-3c9b7f3bc990")),
        name={"en": "bathymetry", "pt": "batimetria"},
    ),
    "backscatter": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("3002d462-3f2e-4957-a56e-97175f91883a")),
        name={"en": "backscatter", "pt": "backscatter"},
    ),
    "seismic": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("53ec7259-5fbe-48d7-9d1b-508225add0a0")),
        name={"en": "seismic", "pt": "sísmica"},
    ),
    "magnetometer/gradiometer": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("333073eb-adc9-4ac7-b822-44f4df5575a3")),
        name={"en": "magnetometer/gradiometer", "pt": "magnetómetro/gradiómetro"},
    ),
    "superficial sediment samples": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("4b17a645-dc10-488c-ba7d-47ff052efdf8")),
        name={
            "en": "superficial sediment samples",
            "pt": "amostras sedimento superficiais",
        },
    ),
    "cores": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("fd68accf-057e-4813-b47a-aa4df3741c45")),
        name={"en": "cores", "pt": "núcleos"},
    ),
    "CPT tests": schemas.DatasetCategoryCreate(
        id=schemas.DatasetCategoryId(uuid.UUID("43507846-a6cf-4e54-bd80-9ef5be334cf0")),
        name={"en": "CPT tests", "pt": "tests CPT"},
    ),
}

DOMAIN_TYPES_TO_CREATE: dict[str, schemas.DomainTypeCreate] = {
    "geophysical": schemas.DomainTypeCreate(
        id=schemas.DomainTypeId(uuid.UUID("b06335e1-e8c2-4d27-9b20-5c3530fd4576")),
        name={"en": "geophysical", "pt": "geofísica"},
    ),
    "geotechnical": schemas.DomainTypeCreate(
        id=schemas.DomainTypeId(uuid.UUID("474a9110-b8d5-4269-91a7-d8a307bd01c2")),
        name={"en": "geotechnical", "pt": "geotécnica"},
    ),
}

WORKFLOW_STAGES_TO_CREATE: dict[str, schemas.WorkflowStageCreate] = {
    "raw data": schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("ac51aa07-90e9-43d4-83b9-d079482a001e")),
        name={"en": "raw data", "pt": "dados brutos"},
    ),
    "quality control data": schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("6dc042b3-16f9-4a9a-a30a-ac9201b4eb1d")),
        name={"en": "quality control data", "pt": "dados controlo de qualidade"},
    ),
    "processed data": schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("372ac9ed-c7b9-4be3-9030-30149f0b4295")),
        name={"en": "processed data", "pt": "dados processados"},
    ),
    "interpreted data": schemas.WorkflowStageCreate(
        id=schemas.WorkflowStageId(uuid.UUID("342fb236-6622-495e-ae6c-fd90f5cf0d16")),
        name={"en": "interpreted data", "pt": "dados interpretados"},
    ),
}
