import logging
from typing import Protocol

from anyio import Path

from ..db.models import SurveyMission
from ..schemas import discovery as discovery_schemas
from ..schemas import surveyrelatedrecords as record_schemas

logger = logging.getLogger(__name__)


class RecordExtractorProtocol(Protocol):
    async def __call__(
        self,
        survey_mission: SurveyMission,
        asset_paths: list[Path],
        record_configuration: discovery_schemas.SurveyRecordDiscoveryConfiguration,
        record_relations_configuration: discovery_schemas.RecordRelationDiscoveryConfiguration,
    ) -> record_schemas.SurveyRelatedRecordCreate:
        """Discover records and their assets on the filesystem"""
