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
            filters.EnNameFilter,
            "some_name",
            "some_name",
            "en_name_filter",
            "en_name",
            {"en_name_filter": "some_name"},
            "en_name=some_name",
        ),
        pytest.param(
            filters.PtNameFilter,
            "um nome",
            "um nome",
            "pt_name_filter",
            "pt_name",
            {"pt_name_filter": "um nome"},
            "pt_name=um nome",
        ),
        pytest.param(
            filters.DatasetCategoryFilter,
            "cat1",
            "cat1",
            "dataset_category_filter",
            "dataset_category",
            {"dataset_category_filter": "cat1"},
            "dataset_category=cat1",
        ),
        pytest.param(
            filters.DomainTypeFilter,
            "dt1",
            "dt1",
            "domain_type_filter",
            "domain_type",
            {"domain_type_filter": "dt1"},
            "domain_type=dt1",
        ),
        pytest.param(
            filters.WorkflowStageFilter,
            "ws1",
            "ws1",
            "workflow_stage_filter",
            "workflow_stage",
            {"workflow_stage_filter": "ws1"},
            "workflow_stage=ws1",
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
    filter_ = filters.EnNameFilter.from_params({"en_name": value})
    assert filter_.value == value


@pytest.mark.parametrize(
    "filter_, expected_qs_fragment",
    [
        pytest.param(
            filters.ProjectListFilters.from_params({"en_name": "a name"}, "fake_lang"),
            "?en_name=a name",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params({"en_name": ""}, "fake_lang"), ""
        ),
        pytest.param(
            filters.ProjectListFilters.from_params({"pt_name": "um nome"}, "fake_lang"),
            "?pt_name=um nome",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params({"pt_name": ""}, "fake_lang"), ""
        ),
        pytest.param(filters.ProjectListFilters.from_params({}, "fake_lang"), ""),
        pytest.param(
            filters.ProjectListFilters.from_params({"search": "stuffs"}, "fake_lang"),
            "?fake_lang_name=stuffs",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params({"search": ""}, "fake_lang"), ""
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs",
                    "minLon": "0",
                    "minLat": "0",
                    "maxLon": "10",
                    "maxLat": "10",
                },
                "fake_lang",
            ),
            "?minLon=0.0&minLat=0.0&maxLon=10.0&maxLat=10.0&fake_lang_name=stuffs",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs1",
                    "en_name": "stuffs2",
                },
                "fake_lang",
            ),
            "?en_name=stuffs2&fake_lang_name=stuffs1",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {
                    "search": "stuffs1",
                    "en_name": "stuffs2",
                },
                "en",
            ),
            "?en_name=stuffs1",
            id="search_overrides_name",
        ),
        pytest.param(
            filters.ProjectListFilters.from_params(
                {"minLon": "0", "minLat": "0", "maxLon": "0", "maxLat": "0"},
                "fake_lang",
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
                },
                "fake_lang",
            ),
            "?fake_lang_name=stuffs",
            id="invalid_bbox",
        ),
    ],
)
def test_project_list_filter_serialization(
    filter_: filters.SimpleListFilter, expected_qs_fragment
):
    assert filter_.serialize_to_query_string() == expected_qs_fragment
