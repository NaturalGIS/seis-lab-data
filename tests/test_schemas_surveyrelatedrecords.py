"""Assets and previews of survey-related records

The assets of a survey-related record get a media type derived from their file extension
when none is given, and their names must be unique within the record. The previews
generated for a record are shown in the record list and on the record's page.
"""

import uuid

import pytest
import shapely

from seis_lab_data import constants
from seis_lab_data.db.commands import recordassets as asset_commands
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import surveyrelatedrecords as record_schemas


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
    """The media type of an asset is derived from its file extension, regardless of
    letter case; a path without an extension, or an empty path, yields no media type.
    """
    assert record_schemas.derive_media_type(relative_path) == expected


@pytest.mark.parametrize(
    "media_type",
    [
        pytest.param(None),
        pytest.param(""),
    ],
)
def test_record_asset_create_derives_missing_media_type(media_type):
    """A new asset without a media type gets one derived from its file extension."""
    asset = record_schemas.DataRecordAssetCreate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        name="An asset",
        description="An asset",
        media_type=media_type,
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "application/prs.ipma.tif"


def test_record_asset_create_keeps_explicit_media_type():
    """A new asset keeps the media type it is given, rather than one derived from its
    file extension.
    """
    asset = record_schemas.DataRecordAssetCreate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        name="An asset",
        description="An asset",
        media_type="image/tiff",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "image/tiff"


def test_record_asset_update_derives_blank_media_type():
    """Editing an asset with a blank media type gives it a media type derived from its
    file extension.
    """
    # the update form always submits the field, currently as an empty string
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "application/prs.ipma.tif"


def test_record_asset_update_leaves_unsent_media_type_alone():
    """Editing an asset without supplying a media type leaves its stored media type
    unchanged.
    """
    # deriving it here would add the field to the set of values to be applied,
    # thereby overwriting whatever media type is already stored
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        relative_path="s01/grid.tif",
    )
    assert asset.media_type is None
    assert "media_type" not in asset.model_dump(exclude_unset=True)


def test_record_asset_update_without_relative_path_has_no_media_type_to_derive():
    """Editing an asset with a blank media type and no file path leaves the media type
    blank, as there is no file extension to derive it from.
    """
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="",
    )
    assert asset.media_type == ""


def test_record_asset_update_keeps_explicit_media_type():
    """Editing an asset keeps the media type it is given, rather than one derived from
    its file extension.
    """
    asset = record_schemas.DataRecordAssetUpdate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        media_type="image/tiff",
        relative_path="s01/grid.tif",
    )
    assert asset.media_type == "image/tiff"


def test_record_asset_relative_path_is_stripped():
    """Spaces around the file path of an asset, as well as a leading slash, are removed,
    both when the asset is created and when it is edited, before its media type is
    derived from the file extension.
    """
    # a pasted path with a trailing space broke preview eligibility and extraction, and a
    # leading slash made the path absolute, which left out the archive and mission
    # directories when downloading the file
    pasted_path = "  /s01/x.tif  "
    created = record_schemas.DataRecordAssetCreate(
        id=identifiers.RecordAssetId(uuid.uuid4()),
        name="An asset",
        relative_path=pasted_path,
    )
    updated = record_schemas.SurveyRelatedRecordUpdate(
        assets=[{"id": uuid.uuid4(), "media_type": "", "relative_path": pasted_path}]
    ).assets[0]
    for asset in (created, updated):
        assert asset.relative_path == "s01/x.tif"
        # stripped before the media type is derived from the file extension
        assert asset.media_type == "application/prs.ipma.tif"


def test_derived_record_asset_create_requires_data():
    """A generated asset, such as a preview image, cannot be created without its
    content.
    """
    with pytest.raises(ValueError, match=r"data\s+Field required"):
        record_schemas.DerivedRecordAssetCreate(
            id=identifiers.RecordAssetId(uuid.uuid4()),
            name="A preview",
            media_type="image/webp",
            asset_type=[constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_schemas_expose_a_records_derived_asset(
    sample_survey_related_records, db_session_maker
):
    """When a record has several generated previews, the first one by name is shown as
    its thumbnail in the record list and as its preview on the record's page, where the
    map places it over the record's bounding box.
    """
    # list card and detail map both need to reach the preview image, whose
    # bounds on the map are the record's bbox
    first_record, _second_record = sample_survey_related_records
    preview_id = identifiers.RecordAssetId(uuid.uuid4())
    async with db_session_maker() as session:
        await record_commands.bulk_update_manually_selected_records(
            session,
            record_schemas.SurveyRelatedRecordBulkUpdate(
                bbox_4326=shapely.box(-9.7, 39.8, -9.3, 40.5).wkt
            ),
            [identifiers.SurveyRelatedRecordId(first_record.id)],
        )
        await asset_commands.replace_derived_record_assets(
            session,
            first_record,
            [
                # listed first but alphabetically last
                # derived assets by name, not by list or insertion order
                record_schemas.DerivedRecordAssetCreate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name="Z preview",
                    media_type="image/webp",
                    asset_type=[
                        constants.AssetType.THUMBNAIL,
                        constants.AssetType.PREVIEW,
                    ],
                    data=b"not a webp",
                ),
                record_schemas.DerivedRecordAssetCreate(
                    id=preview_id,
                    name="A preview",
                    media_type="image/webp",
                    asset_type=[
                        constants.AssetType.THUMBNAIL,
                        constants.AssetType.PREVIEW,
                    ],
                    data=b"not a webp",
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
    """A record without generated previews shows neither a thumbnail in the record list
    nor a preview on its page, as data files are never shown as previews.
    """
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
    """Several assets of a record can be edited together without changing their names,
    and are not then considered to share the same name.
    """
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


def test_survey_related_record_update_rejects_duplicate_asset_names():
    """A survey-related record cannot have two assets with the same name."""
    with pytest.raises(ValueError, match="Duplicate asset name found"):
        record_schemas.SurveyRelatedRecordUpdate(
            assets=[
                record_schemas.DataRecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name="Same name",
                    relative_path="first-asset",
                ),
                record_schemas.DataRecordAssetUpdate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name="Same name",
                    relative_path="second-asset",
                ),
            ]
        )
