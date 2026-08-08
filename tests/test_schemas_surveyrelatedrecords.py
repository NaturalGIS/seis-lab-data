import uuid

import pytest

from seis_lab_data.schemas import (
    common as common_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
)


def test_survey_related_record_update_allows_multiple_assets_with_unset_names():
    # a partial asset update that doesn't touch the name must not be treated
    # as colliding with other assets that also don't touch their name
    record_schemas.SurveyRelatedRecordUpdate(
        assets=[
            record_schemas.RecordAssetUpdate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                relative_path="first-asset",
            ),
            record_schemas.RecordAssetUpdate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                relative_path="second-asset",
            ),
        ]
    )


def test_survey_related_record_update_rejects_duplicate_asset_english_names():
    with pytest.raises(ValueError, match="Duplicate asset english name found"):
        record_schemas.SurveyRelatedRecordUpdate(
            assets=[
                record_schemas.RecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(en="Same name"),
                    relative_path="first-asset",
                ),
                record_schemas.RecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(en="Same name"),
                    relative_path="second-asset",
                ),
            ]
        )
