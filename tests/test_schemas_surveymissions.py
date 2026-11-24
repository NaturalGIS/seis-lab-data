"""Coordinate reference system and directory of survey missions

A survey mission declares, as an EPSG code, the coordinate reference system assumed for
its files whose format cannot state one. Only codes of usable reference systems are
accepted. Its directory is stored as a path relative to the file archive.
"""

import uuid

import pydantic
import pytest

from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import surveymissions as mission_schemas


@pytest.mark.parametrize(
    "implicit_crs",
    [
        pytest.param(4326, id="geographic"),
        pytest.param(3763, id="projected"),
    ],
)
def test_survey_mission_create_accepts_epsg_code(implicit_crs):
    """A survey mission accepts the EPSG code of a geographic or a projected coordinate
    reference system.
    """
    mission = mission_schemas.SurveyMissionCreate(
        id=identifiers.SurveyMissionId(uuid.uuid4()),
        project_id=identifiers.ProjectId(uuid.uuid4()),
        name="A survey mission",
        description="A survey mission",
        relative_path="a-survey-mission",
        implicit_crs=implicit_crs,
    )
    assert mission.implicit_crs == implicit_crs


@pytest.mark.parametrize(
    "implicit_crs",
    [
        pytest.param(999999, id="unknown"),
        pytest.param(4978, id="geocentric"),
        pytest.param(5714, id="vertical"),
        pytest.param(2**31, id="beyond_c_int"),
    ],
)
def test_survey_mission_create_rejects_unusable_epsg_code(implicit_crs):
    """A survey mission rejects an EPSG code that is unknown, out of range, or that of a
    geocentric or vertical reference system, and the error is shown on the coordinate
    reference system field.
    """
    with pytest.raises(pydantic.ValidationError) as exc_info:
        mission_schemas.SurveyMissionCreate(
            id=identifiers.SurveyMissionId(uuid.uuid4()),
            project_id=identifiers.ProjectId(uuid.uuid4()),
            name="A survey mission",
            description="A survey mission",
            relative_path="a-survey-mission",
            implicit_crs=implicit_crs,
        )
    # the form maps errors back to its fields by this location
    assert [error["loc"] for error in exc_info.value.errors()] == [("implicit_crs",)]


def test_survey_mission_relative_path_is_stripped():
    """Spaces around the directory path of a survey mission, as well as a leading slash,
    are removed, both when the survey mission is created and when it is edited.
    """
    # a leading slash made the path absolute, which left out the archive directory when
    # downloading the files of the survey mission's records
    pasted_path = "  /surveys/a-survey-mission  "
    created = mission_schemas.SurveyMissionCreate(
        id=identifiers.SurveyMissionId(uuid.uuid4()),
        project_id=identifiers.ProjectId(uuid.uuid4()),
        name="A survey mission",
        description="A survey mission",
        relative_path=pasted_path,
    )
    updated = mission_schemas.SurveyMissionUpdate(relative_path=pasted_path)
    for mission in (created, updated):
        assert mission.relative_path == "surveys/a-survey-mission"
