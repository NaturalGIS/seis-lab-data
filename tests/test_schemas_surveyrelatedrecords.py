import uuid

import pytest
import shapely

from seis_lab_data import constants
from seis_lab_data.db.commands import recordassets as asset_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.schemas import (
    common as common_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
)


@pytest.mark.parametrize(
    "relative_path, expected",
    [
        pytest.param("s01/grid.tif", "application/prs.ipma.tif"),
        pytest.param("s01/FOO.TIF", "application/prs.ipma.tif"),
        pytest.param("s01/no-extension", None),
        pytest.param("s01/trailing-dot.", None),
        pytest.param(".hidden", "application/prs.ipma.hidden"),
        pytest.param("", None),
    ],
)
def test_derive_media_type(relative_path, expected):
    assert record_schemas.derive_media_type(relative_path) == expected


@pytest.mark.parametrize(
    "media_type",
    [
        pytest.param(None),
        pytest.param(""),
    ],
)
def test_record_asset_create_derives_missing_media_type(media_type):
    asset = record_schemas.DataRecordAssetCreate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        name=common_schemas.LocalizableDraftName(en="An asset"),
        description=common_schemas.LocalizableDraftDescription(en="An asset"),
        media_type=media_type,
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "application/prs.ipma.tif"


def test_record_asset_create_keeps_explicit_media_type():
    asset = record_schemas.DataRecordAssetCreate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        name=common_schemas.LocalizableDraftName(en="An asset"),
        description=common_schemas.LocalizableDraftDescription(en="An asset"),
        media_type="image/tiff",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "image/tiff"


def test_record_asset_update_derives_blank_media_type():
    # the update form always submits the field, currently as an empty string
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "application/prs.ipma.tif"


def test_record_asset_update_leaves_unsent_media_type_alone():
    # deriving it here would add the field to the set of values to be applied,
    # thereby overwriting whatever media type is already stored
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        relative_path="s01/grid.tif",
    )
    assert asset.media_type is None
    assert "media_type" not in asset.model_dump(exclude_unset=True)


def test_record_asset_update_without_relative_path_has_no_media_type_to_derive():
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="",
    )
    assert asset.media_type == ""


def test_record_asset_update_keeps_explicit_media_type():
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="image/tiff",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "image/tiff"


def test_derived_record_asset_create_requires_data_or_geog():
    with pytest.raises(ValueError, match="Either data or geog must be provided"):
        record_schemas.DerivedRecordAssetCreate(
            id=identifiers.RecordAssetId(uuid.uuid4()),
            name=common_schemas.LocalizableDraftName(en="A preview"),
            media_type="image/webp",
            asset_type=[constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_schemas_expose_a_records_derived_asset(
    sample_survey_related_records, db_session_maker
):
    # list card and detail map both need to reach preview image, and
    # its bounds are the image's, not the record's bbox
    first_record, _second_record = sample_survey_related_records
    preview_id = identifiers.RecordAssetId(uuid.uuid4())
    async with db_session_maker() as session:
        await asset_commands.replace_derived_record_assets(
            session,
            first_record,
            [
                # listed first but alphabetically last
                # derived assets by name, not by list or insertion order
                record_schemas.DerivedRecordAssetCreate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(en="Z preview"),
                    media_type="image/webp",
                    asset_type=[
                        constants.AssetType.THUMBNAIL,
                        constants.AssetType.PREVIEW,
                    ],
                    data=b"not a webp",
                    geog=shapely.box(0.0, 0.0, 1.0, 1.0).wkt,
                ),
                record_schemas.DerivedRecordAssetCreate(
                    id=preview_id,
                    name=common_schemas.LocalizableDraftName(en="A preview"),
                    media_type="image/webp",
                    asset_type=[
                        constants.AssetType.THUMBNAIL,
                        constants.AssetType.PREVIEW,
                    ],
                    data=b"not a webp",
                    geog=shapely.box(-9.7, 39.8, -9.3, 40.5).wkt,
                ),
            ],
        )
        record = await record_queries.get_survey_related_record(
            session, identifiers.SurveyRelatedRecordId(first_record.id)
        )
    list_item = record_schemas.SurveyRelatedRecordReadListItem.from_db_instance(record)
    detail = record_schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        record, [], []
    )
    assert list_item.thumbnail_asset_id == preview_id
    assert detail.preview_asset_id == preview_id
    assert detail.preview_bounds.bounds == pytest.approx((-9.7, 39.8, -9.3, 40.5))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_schemas_have_no_preview_without_derived_assets(
    sample_survey_related_records, db_session_maker
):
    # sample records only have data assets, which are never shown as previews
    first_record, _second_record = sample_survey_related_records
    async with db_session_maker() as session:
        record = await record_queries.get_survey_related_record(
            session, identifiers.SurveyRelatedRecordId(first_record.id)
        )
    list_item = record_schemas.SurveyRelatedRecordReadListItem.from_db_instance(record)
    detail = record_schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        record, [], []
    )
    assert list_item.thumbnail_asset_id is None
    assert detail.preview_asset_id is None
    assert detail.preview_bounds is None


def test_survey_related_record_update_allows_multiple_assets_with_unset_names():
    # a partial asset update that doesn't touch the name must not be treated
    # as colliding with other assets that also don't touch their name
    record_schemas.SurveyRelatedRecordUpdate(
        assets=[
            record_schemas.DataRecordAssetUpdate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                relative_path="first-asset",
            ),
            record_schemas.DataRecordAssetUpdate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                relative_path="second-asset",
            ),
        ]
    )


def test_survey_related_record_update_rejects_duplicate_asset_english_names():
    with pytest.raises(ValueError, match="Duplicate asset english name found"):
        record_schemas.SurveyRelatedRecordUpdate(
            assets=[
                record_schemas.DataRecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(en="Same name"),
                    relative_path="first-asset",
                ),
                record_schemas.DataRecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(en="Same name"),
                    relative_path="second-asset",
                ),
            ]
        )
