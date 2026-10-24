import uuid

import shapely
import pytest

from seis_lab_data.webapp import filters


@pytest.mark.parametrize(
    [
        "type_",
        "value",
        "expected_value",
        "expected_internal_name",
        "expected_public_name",
        "expected_kwargs",
        "expected_qs",
    ],
    [
        pytest.param(
            filters.NameFilter,
            "some_name",
            "some_name",
            "name_filter",
            "search",
            {"name_filter": "some_name"},
            "search=some_name",
        ),
        pytest.param(
            filters.DatasetCategoryFilter,
            "cat1",
            "cat1",
            "dataset_category_id",
            "filterDatasetCategory",
            {"dataset_category_id": "cat1"},
            "filterDatasetCategory=cat1",
        ),
        pytest.param(
            filters.WorkflowStageFilter,
            "ws1",
            "ws1",
            "workflow_stage_id",
            "filterWorkflowStage",
            {"workflow_stage_id": "ws1"},
            "filterWorkflowStage=ws1",
        ),
    ],
)
def test_simple_filter(
    type_,
    value,
    expected_value,
    expected_internal_name,
    expected_public_name,
    expected_kwargs,
    expected_qs,
):
    filter_ = type_(value=value)
    assert filter_.value == expected_value
    assert filter_.internal_name == expected_internal_name
    assert filter_.public_name == expected_public_name
    assert filter_.as_kwargs() == expected_kwargs
    assert filter_.serialize_to_query_string() == expected_qs


def test_bounding_box_filter():
    bbox_wkt = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
    filter_ = filters.BoundingBoxFilter(value=shapely.from_wkt(bbox_wkt))
    assert filter_.value.wkt == bbox_wkt
    assert filter_.internal_name == "spatial_intersect"
    assert filter_.as_kwargs() == {"spatial_intersect": shapely.from_wkt(bbox_wkt)}
    assert (
        filter_.serialize_to_query_string()
        == "minLon=0.0&minLat=0.0&maxLon=10.0&maxLat=10.0"
    )


def test_simple_filter_from_params():
    value = "fake_value"
    filter_ = filters.NameFilter.from_params({"search": value})
    assert filter_.value == value


@pytest.mark.parametrize(
    "type_, public_name",
    [
        pytest.param(filters.ProjectCompoundNameFilter, "filterProject"),
        pytest.param(filters.SurveyMissionCompoundNameFilter, "filterMission"),
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        pytest.param({}, id="param_absent"),
        pytest.param({"filterProject": "", "filterMission": ""}, id="param_empty"),
        pytest.param(
            {"filterProject": "some name", "filterMission": "some name"},
            id="param_without_trailing_uuid",
        ),
    ],
)
def test_compound_name_filter_from_params_raises_when_no_match(
    type_, public_name, params
):
    # regression test: these filter classes must raise ValueError (like every
    # other SimpleListFilter) when their query param is absent or malformed,
    # instead of silently returning `value=None`. Returning a value in this
    # case used to make `ItemListFilters.as_kwargs()` always emit
    # `survey_mission_id`/`project_id`, even when the caller never asked for
    # mission/project scoping - which collided with routes that also pass
    # `survey_mission_id`/`project_id` explicitly (e.g.
    # `get_mission_records_list_component`), causing
    # `TypeError: got multiple values for keyword argument`.
    with pytest.raises(ValueError):
        type_.from_params(params)


def test_project_compound_name_filter_from_params_parses_valid_compound_name():
    project_id = uuid.uuid4()
    filter_ = filters.ProjectCompoundNameFilter.from_params(
        {"filterProject": f"some project name {project_id}"}
    )
    assert filter_.value == project_id
    assert filter_.as_kwargs() == {"project_id": project_id}


def test_survey_mission_compound_name_filter_from_params_parses_valid_compound_name():
    mission_id = uuid.uuid4()
    filter_ = filters.SurveyMissionCompoundNameFilter.from_params(
        {"filterMission": f"some mission name {mission_id}"}
    )
    assert filter_.value == mission_id
    assert filter_.as_kwargs() == {"survey_mission_id": mission_id}


def test_survey_related_record_list_filters_omits_survey_mission_id_when_unset():
    # regression test for the bug described above: when the caller only
    # supplies unrelated params (e.g. just a free-text search), the resulting
    # kwargs must not contain `survey_mission_id`/`project_id` at all, since
    # some routes (like the mission-scoped records listing) also pass
    # `survey_mission_id` explicitly and would blow up on a duplicate kwarg.
    list_filters = filters.SurveyRelatedRecordListFilters.from_params(
        {"search": "something not matching"}
    )
    kwargs = list_filters.as_kwargs()
    assert "survey_mission_id" not in kwargs
    assert "project_id" not in kwargs
    assert kwargs["name_filter"] == "something not matching"


def test_survey_related_record_list_filters_includes_survey_mission_id_when_set():
    mission_id = uuid.uuid4()
    list_filters = filters.SurveyRelatedRecordListFilters.from_params(
        {"filterMission": f"some mission name {mission_id}"}
    )
    kwargs = list_filters.as_kwargs()
    assert kwargs["survey_mission_id"] == mission_id


@pytest.mark.parametrize(
    "filter_, expected_qs_fragment",
    [
        pytest.param(filters.ProjectListFilters.from_params({}), ""),
        pytest.param(
            filters.ProjectListFilters.from_params({"search": "stuffs"}),
            "?search=stuffs",
        ),
        pytest.param(filters.ProjectListFilters.from_params({"search": ""}), ""),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs",
                    "minLon": "0",
                    "minLat": "0",
                    "maxLon": "10",
                    "maxLat": "10",
                }
            ),
            "?minLon=0.0&minLat=0.0&maxLon=10.0&maxLat=10.0&search=stuffs",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {"minLon": "0", "minLat": "0", "maxLon": "0", "maxLat": "0"}
            ),
            "",
            id="only_invalid_bbox",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs",
                    "minLon": "0",
                    "minLat": "0",
                    "maxLon": "0",
                    "maxLat": "0",
                }
            ),
            "?search=stuffs",
            id="invalid_bbox",
        ),
    ],
)
def test_project_list_filter_serialization(
    filter_: filters.SimpleListFilter, expected_qs_fragment
):
    assert filter_.serialize_to_query_string() == expected_qs_fragment
