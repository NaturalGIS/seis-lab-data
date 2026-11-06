import uuid

import pydantic
import pytest

from seis_lab_data.schemas import (
    identifiers,
    surveymissions as mission_schemas,
)


@pytest.mark.parametrize(
    "implicit_crs",
    [
        pytest.param(4326, id="geographic"),
        pytest.param(3763, id="projected"),
    ],
)
def test_survey_mission_create_accepts_epsg_code(implicit_crs):
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
