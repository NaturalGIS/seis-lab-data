import uuid
from typing import NewType

AssetDiscoveryConfId = NewType("AssetDiscoveryConfId", uuid.UUID)
DatasetCategoryId = NewType("DatasetCategoryId", uuid.UUID)
RecordAssetId = NewType("RecordAssetId", uuid.UUID)
RecordDiscoveryConfId = NewType("RecordDiscoveryConfId", str)
RequestId = NewType("RequestId", uuid.UUID)
SurveyRelatedRecordId = NewType("SurveyRelatedRecordId", uuid.UUID)
SurveyMissionId = NewType("SurveyMissionId", uuid.UUID)
ProjectId = NewType("ProjectId", uuid.UUID)
UserId = NewType("UserId", str)
WorkflowStageId = NewType("WorkflowStageId", uuid.UUID)
