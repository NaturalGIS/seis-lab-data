from typing import Protocol

from ...schemas.discovery import SurveyRecordDiscoveryConfiguration
from ...schemas.surveyrelatedrecords import SurveyRelatedRecordCreate


class NewRecordExtractorProtocol(Protocol):
    async def __call__(
        self,
        initial_record: SurveyRelatedRecordCreate,
        record_configuration: SurveyRecordDiscoveryConfiguration,
    ) -> SurveyRelatedRecordCreate:
        """Extract relevant metadata from the record's assets"""
