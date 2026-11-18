"""Search filters in the page address

List pages can be filtered by name, dataset category, workflow stage, status, project,
survey mission, temporal extent and map area. Filters are kept in the page address, so
that a filtered list can be reloaded or shared.
"""

import urllib.parse
import uuid

import pytest
import shapely

from seis_lab_data import constants
from seis_lab_data.webapp import filters


@pytest.mark.parametrize(
    [
        "type_",
        "value",
        "expected_value",
        "expected_internal_name",
        "expected_public_name",
        "expected_kwargs",
        "expected_query_params",
    ],
    [
        pytest.param(
            filters.NameFilter,
            "some_name",
            "some_name",
            "name_filter",
            "search",
            {"name_filter": "some_name"},
            {"search": "some_name"},
        ),
        pytest.param(
            filters.DatasetCategoryFilter,
            "cat1",
            "cat1",
            "dataset_category_id",
            "filterDatasetCategory",
            {"dataset_category_id": "cat1"},
            {"filterDatasetCategory": "cat1"},
        ),
        pytest.param(
            filters.WorkflowStageFilter,
            "ws1",
            "ws1",
            "workflow_stage_id",
            "filterWorkflowStage",
            {"workflow_stage_id": "ws1"},
            {"filterWorkflowStage": "ws1"},
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
    expected_query_params,
):
    """The name, dataset category and workflow stage filters keep their value and are
    written to the page address under their public names.
    """
    filter_ = type_(value=value)
    assert filter_.value == expected_value
    assert filter_.internal_name == expected_internal_name
    assert filter_.public_name == expected_public_name
    assert filter_.as_kwargs() == expected_kwargs
    assert filter_.serialize_to_query_params() == expected_query_params


def test_bounding_box_filter():
    """The map area filter keeps its bounding box and is written to the page address as
    the map area switch and the four corner coordinates.
    """
    bbox_wkt = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
    filter_ = filters.BoundingBoxFilter(value=shapely.from_wkt(bbox_wkt))
    assert filter_.value.wkt == bbox_wkt
    assert filter_.internal_name == "spatial_intersect"
    assert filter_.as_kwargs() == {"spatial_intersect": shapely.from_wkt(bbox_wkt)}
    assert filter_.serialize_to_query_params() == {
        "filterByMapArea": "true",
        "minLon": "0.0",
        "minLat": "0.0",
        "maxLon": "10.0",
        "maxLat": "10.0",
    }


def test_simple_filter_from_params():
    """The name filter is read from the search term in the page address."""
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
    """The project and survey mission filters are not applied when the page address
    lacks them or does not carry a valid identifier in them.
    """
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
    """The project filter recognizes the project from the identifier that follows its
    name in the page address.
    """
    project_id = uuid.uuid4()
    filter_ = filters.ProjectCompoundNameFilter.from_params(
        {"filterProject": f"some project name {project_id}"}
    )
    assert filter_.value == project_id
    assert filter_.as_kwargs() == {"project_id": project_id}


def test_survey_mission_compound_name_filter_from_params_parses_valid_compound_name():
    """The survey mission filter recognizes the survey mission from the identifier that
    follows its name in the page address.
    """
    mission_id = uuid.uuid4()
    filter_ = filters.SurveyMissionCompoundNameFilter.from_params(
        {"filterMission": f"some mission name {mission_id}"}
    )
    assert filter_.value == mission_id
    assert filter_.as_kwargs() == {"survey_mission_id": mission_id}


def test_survey_related_record_list_filters_omits_survey_mission_id_when_unset():
    """When only a search term is given, the record list is not restricted to any
    project or survey mission.
    """
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
    """When a survey mission filter is given, the record list is restricted to that
    survey mission.
    """
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
                    "filterByMapArea": "true",
                    "minLon": "0",
                    "minLat": "0",
                    "maxLon": "10",
                    "maxLat": "10",
                }
            ),
            "?filterByMapArea=true&minLon=0.0&minLat=0.0&maxLon=10.0&maxLat=10.0&search=stuffs",
        ),
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
            "?search=stuffs",
            id="bbox_without_map_area_switch",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "filterByMapArea": "true",
                    "minLon": "0",
                    "minLat": "0",
                    "maxLon": "0",
                    "maxLat": "0",
                }
            ),
            "",
            id="only_invalid_bbox",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs",
                    "filterByMapArea": "true",
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
    """The project list writes only its effective filters to the page address: empty
    search terms, map areas without the map area switch and invalid map areas are left
    out.
    """
    assert filter_.serialize_to_query_string() == expected_qs_fragment


@pytest.mark.parametrize(
    "list_filters_type, params",
    [
        pytest.param(
            filters.SurveyRelatedRecordListFilters,
            {
                "filterProject": f"A project - {uuid.uuid4()}",
                "filterMission": f"A mission (A project) - {uuid.uuid4()}",
            },
            id="compound_names",
        ),
        pytest.param(
            filters.SurveyRelatedRecordListFilters,
            {
                "search": "a&b=c #d",
                "assetPathFragment": "some/path?x=1",
                "filterMediaType": "image/tiff; application=geotiff",
            },
            id="reserved_characters",
        ),
        pytest.param(
            filters.SurveyRelatedRecordListFilters,
            {"filterStatus": "under_export"},
            id="record_status",
        ),
        pytest.param(
            filters.ProjectListFilters,
            {
                "filterStatus": "draft",
                "temporalExtentBegin": "2020-01-01",
                "temporalExtentEnd": "2021-12-31",
                "filterByMapArea": "true",
                "minLon": "-10.5",
                "minLat": "36.0",
                "maxLon": "-6.0",
                "maxLat": "42.0",
            },
            id="project_status_temporal_and_map_area",
        ),
    ],
)
def test_list_filters_survive_a_query_string_round_trip(list_filters_type, params):
    """Filters written to the page address are read back unchanged when the page is
    reloaded, including names with special characters, statuses, temporal extents and
    map areas.
    """
    # the page URL is updated with the serialized filters - reloading the page
    # parses them again from it
    list_filters = list_filters_type.from_params(params)
    query_string = list_filters.serialize_to_query_string()
    reparsed = list_filters_type.from_params(
        dict(urllib.parse.parse_qsl(query_string.removeprefix("?")))
    )
    assert reparsed.as_kwargs() == list_filters.as_kwargs()
    assert reparsed.serialize_to_query_string() == query_string


@pytest.mark.parametrize(
    "list_filters_type, status_value, expected_status",
    [
        pytest.param(
            filters.ProjectListFilters, "draft", constants.ProjectStatus.DRAFT
        ),
        pytest.param(
            filters.SurveyMissionListFilters,
            "cancelling_discovery",
            constants.SurveyMissionStatus.CANCELLING_DISCOVERY,
        ),
        pytest.param(
            filters.SurveyRelatedRecordListFilters,
            "under_derivation",
            constants.SurveyRelatedRecordStatus.UNDER_DERIVATION,
        ),
    ],
)
def test_status_filter_parses_the_entity_status(
    list_filters_type, status_value, expected_status
):
    """The status filter of each list page recognizes the statuses of its own kind of
    entry, including processing states.
    """
    list_filters = list_filters_type.from_params({"filterStatus": status_value})
    assert list_filters.as_kwargs()["status"] is expected_status


@pytest.mark.parametrize(
    "list_filters_type, status_value",
    [
        pytest.param(filters.ProjectListFilters, "all", id="all_option"),
        pytest.param(filters.ProjectListFilters, "", id="empty"),
        # a record status, which projects do not have
        pytest.param(filters.ProjectListFilters, "under_export", id="foreign_status"),
        pytest.param(filters.SurveyMissionListFilters, "bogus", id="unknown_status"),
    ],
)
def test_status_filter_ignores_values_which_are_not_a_status(
    list_filters_type, status_value
):
    """The status filter is not applied when its value is the option for all statuses,
    empty, unknown, or a status belonging to another kind of entry.
    """
    list_filters = list_filters_type.from_params({"filterStatus": status_value})
    assert "status" not in list_filters.as_kwargs()


@pytest.mark.parametrize(
    "switch_value, expected_applied",
    [
        pytest.param(True, True, id="json_true"),
        pytest.param("true", True, id="query_string_true"),
        pytest.param(False, False, id="json_false"),
        pytest.param("false", False, id="query_string_false"),
        pytest.param(None, False, id="absent"),
    ],
)
def test_bounding_box_filter_requires_the_map_area_switch(
    switch_value, expected_applied
):
    """The map area filter is applied only when the map area switch is turned on."""
    params = {"minLon": -10, "minLat": 36, "maxLon": -6, "maxLat": 42}
    if switch_value is not None:
        params["filterByMapArea"] = switch_value
    list_filters = filters.ProjectListFilters.from_params(params)
    assert ("spatial_intersect" in list_filters.as_kwargs()) is expected_applied


@pytest.mark.parametrize(
    "bounds, expected_bounds",
    [
        pytest.param((-10, 36, -6, 42), (-10, 36, -6, 42), id="unchanged"),
        pytest.param((-400, -95, 400, 95), (-180, -90, 180, 90), id="whole_world"),
        pytest.param((350, 36, 354, 42), (-10, 36, -6, 42), id="panned_a_world_east"),
        pytest.param((-370, 36, -366, 42), (-10, 36, -6, 42), id="panned_a_world_west"),
        pytest.param((170, 0, 190, 10), (170, 0, 180, 10), id="across_antimeridian"),
    ],
)
def test_bounding_box_filter_normalizes_map_bounds(bounds, expected_bounds):
    """The map area filter brings the visible map area within valid world coordinates,
    so that a map panned across the world or the antimeridian still filters the intended
    region.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    filter_ = filters.BoundingBoxFilter.from_params(
        {
            "filterByMapArea": True,
            "minLon": min_lon,
            "minLat": min_lat,
            "maxLon": max_lon,
            "maxLat": max_lat,
        }
    )
    assert filter_.value.bounds == pytest.approx(expected_bounds)


def test_survey_mission_list_filters_parse_a_project_compound_name():
    """The survey mission list can be filtered by project, and the project filter is
    kept in the page address.
    """
    project_id = uuid.uuid4()
    compound_name = f"A project - {project_id}"
    list_filters = filters.SurveyMissionListFilters.from_params(
        {"filterProject": compound_name}
    )
    assert list_filters.as_kwargs() == {"project_id": project_id}
    assert list_filters.serialize_to_query_string() == "?" + urllib.parse.urlencode(
        {"filterProject": compound_name}
    )
