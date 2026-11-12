import uuid

import pydantic
import pytest
import shapely
from geoalchemy2 import WKBElement

from seis_lab_data import constants
from seis_lab_data.schemas import (
    identifiers,
    validation as validation_schemas,
)


_BBOX = WKBElement(shapely.to_wkb(shapely.box(-10, 38, -9, 39)), srid=4326)


def _project_data(**overrides) -> dict:
    return {
        "id": identifiers.ProjectId(uuid.uuid4()),
        "name": "A project",
        "description": "A project",
        "status": constants.ProjectStatus.DRAFT,
        "temporal_extent_begin": None,
        "temporal_extent_end": None,
        "bbox_4326": _BBOX,
        **overrides,
    }


def _survey_mission_data(**overrides) -> dict:
    return {
        "id": identifiers.SurveyMissionId(uuid.uuid4()),
        "name": "A survey mission",
        "description": "A survey mission",
        "status": constants.SurveyMissionStatus.DRAFT,
        "temporal_extent_begin": None,
        "temporal_extent_end": None,
        "relative_path": "a-survey-mission",
        "bbox_4326": _BBOX,
        **overrides,
    }


def _survey_related_record_data(**overrides) -> dict:
    return {
        "id": identifiers.SurveyRelatedRecordId(uuid.uuid4()),
        "name": "A survey-related record",
        "dataset_category_id": identifiers.DatasetCategoryId(uuid.uuid4()),
        "workflow_stage_id": identifiers.WorkflowStageId(uuid.uuid4()),
        "description": "A survey-related record",
        "status": constants.SurveyMissionStatus.DRAFT,
        "temporal_extent_begin": None,
        "temporal_extent_end": None,
        "bbox_4326": _BBOX,
        **overrides,
    }


_SCHEMAS_AND_DATA = [
    pytest.param(validation_schemas.ValidProject, _project_data, id="project"),
    pytest.param(
        validation_schemas.ValidSurveyMission,
        _survey_mission_data,
        id="survey_mission",
    ),
    pytest.param(
        validation_schemas.ValidSurveyRelatedRecord,
        _survey_related_record_data,
        id="survey_related_record",
    ),
]


@pytest.mark.parametrize("schema, make_data", _SCHEMAS_AND_DATA)
@pytest.mark.parametrize(
    "description",
    [
        pytest.param("", id="empty"),
        pytest.param("abc", id="short"),
        pytest.param("x" * constants.DESCRIPTION_MAX_LENGTH, id="max_length"),
    ],
)
def test_valid_schemas_accept_optional_description(schema, make_data, description):
    item = schema.model_validate(make_data(description=description))
    assert item.description == description


@pytest.mark.parametrize("schema, make_data", _SCHEMAS_AND_DATA)
def test_valid_schemas_reject_too_long_description(schema, make_data):
    with pytest.raises(pydantic.ValidationError) as exc_info:
        schema.model_validate(
            make_data(description="x" * (constants.DESCRIPTION_MAX_LENGTH + 1))
        )
    assert [e["loc"] for e in exc_info.value.errors()] == [("description",)]


@pytest.mark.parametrize("schema, make_data", _SCHEMAS_AND_DATA)
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("x" * (constants.NAME_MIN_LENGTH - 1), id="too_short"),
        pytest.param("x" * (constants.NAME_MAX_LENGTH + 1), id="too_long"),
    ],
)
def test_valid_schemas_require_name(schema, make_data, name):
    with pytest.raises(pydantic.ValidationError) as exc_info:
        schema.model_validate(make_data(name=name))
    assert [e["loc"] for e in exc_info.value.errors()] == [("name",)]


@pytest.mark.parametrize("schema, make_data", _SCHEMAS_AND_DATA)
def test_valid_schemas_require_spatial_extent(schema, make_data):
    with pytest.raises(pydantic.ValidationError) as exc_info:
        schema.model_validate(make_data(bbox_4326=None))
    assert [e["loc"] for e in exc_info.value.errors()] == [("bbox_4326",)]


@pytest.mark.parametrize("schema, make_data", _SCHEMAS_AND_DATA)
@pytest.mark.parametrize(
    "link_description",
    [
        pytest.param("", id="empty"),
        pytest.param("abc", id="short"),
    ],
)
def test_valid_schemas_accept_optional_link_description(
    schema, make_data, link_description
):
    link = {
        "url": "https://example.com",
        "media_type": "text/html",
        "relation": "related",
        "link_description": link_description,
    }
    item = schema.model_validate(make_data(links=[link]))
    assert item.links[0].link_description == link_description
