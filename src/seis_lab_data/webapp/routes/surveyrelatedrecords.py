import dataclasses
import json
import logging
from typing import (
    AsyncGenerator,
    TypeVar,
)
import uuid

import shapely
from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.sse import DatastarEvent
from datastar_py.starlette import DatastarResponse
from dramatiq import Message
from jinja2 import Template
from redis.asyncio import Redis
from starlette_babel import gettext_lazy as _
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette_wtf import csrf_protect

from ... import (
    config,
    errors,
    operations,
    permissions,
    schemas,
)
from ...db import (
    models,
    queries,
)
from ...processing import tasks
from .. import (
    filters,
    forms,
)
from .auth import (
    get_user,
    fancy_requires_auth,
)
from .common import (
    get_id_from_request_path,
    get_page_from_request_params,
    get_pagination_info,
    produce_event_stream_for_topic,
)

logger = logging.getLogger(__name__)


async def _get_survey_related_record_details(
    request: Request,
) -> schemas.SurveyRelatedRecordDetails:
    """Utility function to get survey-related record details and its assets."""
    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    session_maker = request.state.session_maker
    survey_related_record_id = get_id_from_request_path(
        request, "survey_related_record_id", schemas.SurveyRelatedRecordId
    )
    async with session_maker() as session:
        try:
            survey_related_record = await operations.get_survey_related_record(
                survey_related_record_id,
                user.id if user else None,
                session,
                request.state.settings,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_related_record is None:
            raise HTTPException(
                status_code=404,
                detail=_(
                    f"Survey-related record {survey_related_record_id!r} not found."
                ),
            )
    serialized = schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        survey_related_record
    )
    can_update = await permissions.can_update_survey_related_record(
        user, survey_related_record_id, settings=settings
    )
    return schemas.SurveyRelatedRecordDetails(
        item=serialized,
        permissions=schemas.UserPermissionDetails(
            can_create_children=can_update,
            can_update=can_update,
            can_delete=await permissions.can_delete_survey_related_record(
                user, survey_related_record_id, settings=settings
            ),
        ),
        breadcrumbs=[
            schemas.BreadcrumbItem(name=_("Home"), url=str(request.url_for("home"))),
            schemas.BreadcrumbItem(
                name=_("Projects"), url=str(request.url_for("projects:list"))
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.survey_mission.project.name["en"]),
                url=str(
                    request.url_for(
                        "projects:detail",
                        project_id=survey_related_record.survey_mission.project.id,
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.survey_mission.name["en"]),
                url=str(
                    request.url_for(
                        "survey_missions:detail",
                        survey_mission_id=survey_related_record.survey_mission.id,
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.name["en"]),
            ),
        ],
    )


@fancy_requires_auth
async def get_details_component(request: Request):
    details = await _get_survey_related_record_details(request)
    template_processor = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/detail-component.html"
    )
    rendered = template.render(
        request=request,
        survey_related_record=details.item,
        permissions=details.permissions,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


FormType = TypeVar(
    "FormType",
    bound=forms.FormProtocol,
)


async def build_survey_related_record_form_instance(
    request: Request, form_type: type[FormType]
) -> FormType:
    form_instance = await form_type.from_formdata(request)
    current_language = request.state.language
    async with request.state.session_maker() as session:
        form_instance.dataset_category_id.choices = [
            (dc.id, dc.name.get(current_language, dc.name["en"]))
            for dc in await queries.collect_all_dataset_categories(
                session,
                order_by_clause=models.DatasetCategory.name[current_language].astext,
            )
        ]
        form_instance.domain_type_id.choices = [
            (dt.id, dt.name.get(current_language, dt.name["en"]))
            for dt in await queries.collect_all_domain_types(
                session,
                order_by_clause=models.DomainType.name[current_language].astext,
            )
        ]
        form_instance.workflow_stage_id.choices = [
            (ws.id, ws.name.get(current_language, ws.name["en"]))
            for ws in await queries.collect_all_workflow_stages(
                session,
                order_by_clause=models.WorkflowStage.name[current_language].astext,
            )
        ]
    return form_instance


async def get_record_parent_survey_mission_from_request(
    request: Request,
) -> models.SurveyMission:
    user = get_user(request.session.get("user", {}))
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    async with request.state.session_maker() as session:
        if not (
            survey_mission := await operations.get_survey_mission(
                parent_survey_mission_id, user, session, request.state.settings
            )
        ):
            raise HTTPException(
                404, _(f"Survey mission with id {parent_survey_mission_id} not found.")
            )
    return survey_mission


@csrf_protect
@fancy_requires_auth
async def get_creation_form(request: Request):
    """Show an HTML form for the client to prepare a record creation operation."""
    parent_survey_mission = await get_record_parent_survey_mission_from_request(request)
    survey_mission_id = schemas.SurveyMissionId(parent_survey_mission.id)
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        request=request,
        form=form_instance,
        survey_mission_id=survey_mission_id,
    )
    breadcrumbs_template = template_processor.get_template("breadcrumbs.html")
    rendered_breadcrumbs = breadcrumbs_template.render(
        request=request,
        breadcrumbs=[
            schemas.BreadcrumbItem(name=_("Home"), url=str(request.url_for("home"))),
            schemas.BreadcrumbItem(
                name=_("Projects"), url=str(request.url_for("projects:list"))
            ),
            schemas.BreadcrumbItem(
                name=parent_survey_mission.project.name["en"],
                url=str(
                    request.url_for(
                        "projects:detail", project_id=parent_survey_mission.project.id
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=parent_survey_mission.name["en"],
                url=str(
                    request.url_for(
                        "survey_missions:detail", survey_mission_id=survey_mission_id
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=_("New survey-related record"),
            ),
        ],
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )
        yield ServerSentEventGenerator.patch_elements(
            rendered_breadcrumbs,
            selector=schemas.selector_info.breadcrumbs_selector,
            mode=ElementPatchMode.INNER,
        )
        yield ServerSentEventGenerator.patch_elements(
            _("new survey-related record"),
            selector=schemas.selector_info.page_title_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_creation_form_link(request: Request):
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    form_instance.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_creation_form_link(request: Request):
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    link_index = int(request.query_params.get("link_index", 0))
    form_instance.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_creation_form_asset(request: Request):
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    form_instance.assets.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_creation_form_asset(request: Request):
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    asset_index = int(request.query_params.get("asset_index", 0))
    form_instance.assets.entries.pop(asset_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_creation_form_asset_link(request: Request):
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    asset_index = int(request.path_params["asset_index"])
    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)
    form_instance.assets[asset_index].asset_links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_creation_form_asset_link(request: Request):
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )

    asset_index = int(request.path_params["asset_index"])
    link_index = int(request.query_params.get("link_index", 0))

    form_instance = await forms.SurveyRelatedRecordCreateForm.from_request(request)

    form_instance.assets[asset_index].asset_links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
@fancy_requires_auth
async def get_update_form(request: Request):
    """Show an HTML form for the client to prepare a record update operation."""
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(
        request,
        data={
            "name": {
                "en": details.item.name.en,
                "pt": details.item.name.pt,
            },
            "description": {
                "en": details.item.description.en,
                "pt": details.item.description.pt,
            },
            "dataset_category_id": details.item.dataset_category.id,
            "domain_type_id": details.item.domain_type.id,
            "workflow_stage_id": details.item.workflow_stage.id,
            "relative_path": details.item.relative_path,
            "bounding_box": {
                "min_lon": bbox.bounds[0],
                "min_lat": bbox.bounds[1],
                "max_lon": bbox.bounds[2],
                "max_lat": bbox.bounds[3],
            }
            if (bbox := details.item.bbox_4326)
            else None,
            "links": [
                {
                    "url": li.url,
                    "media_type": li.media_type,
                    "relation": li.relation,
                    "link_description": {
                        "en": li.link_description.en,
                        "pt": li.link_description.pt,
                    },
                }
                for li in details.item.links
            ],
            "assets": [
                {
                    "asset_id": str(ass.id),
                    "asset_name": {
                        "en": ass.name.en,
                        "pt": ass.name.pt,
                    },
                    "asset_description": {
                        "en": ass.description.en,
                        "pt": ass.description.pt,
                    },
                    "relative_path": ass.relative_path,
                    "asset_links": [
                        {
                            "url": ali.url,
                            "media_type": ali.media_type,
                            "relation": ali.relation,
                            "link_description": {
                                "en": ali.link_description.en,
                                "pt": ali.link_description.pt,
                            },
                        }
                        for ali in ass.links
                    ],
                }
                for ass in details.item.record_assets
            ],
        },
    )
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        request=request,
        survey_related_record=details.item,
        form=form_instance,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_update_form_link(request: Request):
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    # TODO: implement some logic to limit the number of links that can be added
    form_instance.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_update_form_link(request: Request):
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    # TODO: Check we are not trying to remove an index that is invalid
    link_index = int(request.query_params.get("link_index", 0))
    form_instance.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_update_form_asset(request: Request):
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    # TODO: implement some logic to limit the number of assets that can be added
    form_instance.assets.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_update_form_asset(request: Request):
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    # TODO: Check we are not trying to remove an index that is invalid
    link_index = int(request.query_params.get("link_index", 0))
    form_instance.asset.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_update_form_asset_link(request: Request):
    details = await _get_survey_related_record_details(request)
    # TODO: Check we have a valid index
    asset_index = int(request.path_params["asset_index"])
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    # TODO: implement some logic to limit the number of links that can be added
    form_instance.assets[asset_index].asset_links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_update_form_asset_link(request: Request):
    details = await _get_survey_related_record_details(request)
    form_instance = await forms.SurveyRelatedRecordUpdateForm.from_request(request)
    try:
        asset_index = int(request.path_params["asset_index"])
        if asset_index < 0 or asset_index >= len(form_instance.assets.entries):
            raise RuntimeError("Invalid asset index")
    except (ValueError, KeyError):
        raise HTTPException(404, "Invalid asset index")
    try:
        link_index = int(request.query_params.get("link_index", 0))
        if link_index < 0 or link_index >= len(
            form_instance.assets[asset_index].links.entries
        ):
            raise RuntimeError("Invalid asset link index")
    except (ValueError, KeyError):
        raise HTTPException(404, "Invalid asset link index")

    form_instance.assets[asset_index].asset_links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/update-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_related_record=details.item,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


async def get_list_component(request: Request):
    if (raw_search_params := request.query_params.get("datastar")) is not None:
        try:
            list_filters = filters.SurveyRelatedRecordListFilters.from_json(
                raw_search_params, request.state.language
            )
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid search params")
        else:
            internal_filter_kwargs = list_filters.as_kwargs()
            filter_query_string = list_filters.serialize_to_query_string()
    else:
        internal_filter_kwargs = {}
        filter_query_string = ""
    logger.debug(f"{internal_filter_kwargs=}")
    current_page = get_page_from_request_params(request)
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    async with session_maker() as session:
        items, num_total = await operations.list_survey_related_records(
            session,
            initiator=user.id if user else None,
            page=current_page,
            page_size=settings.pagination_page_size,
            include_total=True,
            **internal_filter_kwargs,
        )
        num_unfiltered_total = (
            await operations.list_survey_related_records(
                session, initiator=user or None, include_total=True
            )
        )[1]
    pagination_info = get_pagination_info(
        current_page,
        settings.pagination_page_size,
        num_total,
        num_unfiltered_total,
        collection_url=str(request.url_for("survey_related_records:list")),
    )
    template_processor = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/list-component.html"
    )
    rendered = template.render(
        request=request,
        items=[
            schemas.SurveyRelatedRecordReadListItem.from_db_instance(item)
            for item in items
        ],
        update_current_url_with=filter_query_string,
        pagination=pagination_info,
        map_popup_detail_base_url=str(
            request.url_for(
                "survey_related_records:detail", survey_related_record_id="_"
            )
        ).rpartition("/")[0],
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.items_selector,
            mode=ElementPatchMode.REPLACE,
        )

    return DatastarResponse(event_streamer())


class SurveyRelatedRecordCollectionEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        """List survey-related records."""
        current_page = get_page_from_request_params(request)
        current_language = request.state.language
        list_filters = filters.SurveyRelatedRecordListFilters.from_params(
            request.query_params, current_language
        )
        session_maker = request.state.session_maker
        settings: config.SeisLabDataSettings = request.state.settings
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            items, num_total = await operations.list_survey_related_records(
                session,
                initiator=user.id if user else None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
                **list_filters.as_kwargs(),
            )
            num_unfiltered_total = (
                await operations.list_survey_related_records(
                    session, initiator=user or None, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page,
            settings.pagination_page_size,
            num_total,
            num_unfiltered_total,
            collection_url=str(request.url_for("survey_related_records:list")),
        )
        if (current_bbox := list_filters.spatial_intersect_filter) is not None:
            min_lon, min_lat, max_lon, max_lat = current_bbox.value.bounds
        else:
            default_bbox = shapely.from_wkt(settings.webmap_default_bbox_wkt)
            min_lon, min_lat, max_lon, max_lat = default_bbox.bounds
        return template_processor.TemplateResponse(
            request,
            "survey-related-records/list.html",
            context={
                "items": [
                    schemas.SurveyRelatedRecordReadListItem.from_db_instance(item)
                    for item in items
                ],
                "pagination": pagination_info,
                "map_bounds": {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                },
                "breadcrumbs": [
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Survey-related records")),
                ],
                "search_initial_value": list_filters.get_text_search_filter(
                    current_language
                ),
                "map_popup_detail_base_url": str(
                    request.url_for(
                        "survey_related_records:detail", survey_related_record_id="_"
                    )
                ).rpartition("/")[0],
            },
        )


class SurveyRelatedRecordDetailEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        """Get survey-related record details."""
        details = await _get_survey_related_record_details(request)
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "survey-related-records/detail.html",
            context={
                "survey_related_record": details.item,
                "permissions": details.permissions,
                "breadcrumbs": details.breadcrumbs,
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def delete(self, request: Request):
        survey_related_record_id = get_id_from_request_path(
            request, "survey_related_record_id", schemas.SurveyRelatedRecordId
        )
        user = get_user(request.session.get("user", {}))
        async with request.state.session_maker() as session:
            if (
                survey_related_record := await operations.get_survey_related_record(
                    survey_related_record_id,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            ) is None:
                raise HTTPException(
                    status_code=404,
                    detail=_(
                        f"Survey-related record {survey_related_record_id!r} not found."
                    ),
                )

        request_id = schemas.RequestId(uuid.uuid4())
        logger.debug(f"{survey_related_record=}")

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    status=final_message.status.value, message=final_message.message
                ),
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            yield ServerSentEventGenerator.redirect(
                str(
                    request.url_for(
                        "survey_missions:detail",
                        survey_mission_id=survey_related_record.survey_mission_id,
                    )
                )
            )

        async def handle_processing_failure(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    status=final_message.status.value,
                    message=f"ERROR: {final_message.message}",
                ),
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

        async def stream_events():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Deleting survey-related record as a background task...</li>""",
                selector="#feedback > ul",
                mode=ElementPatchMode.APPEND,
            )
            enqueued_message: Message = tasks.delete_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_survey_related_record_id=str(survey_related_record_id),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=f"progress:{request_id}",
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                patch_elements_selector=schemas.selector_info.feedback_selector,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())

    @csrf_protect
    @fancy_requires_auth
    async def put(self, request: Request):
        """Update an existing survey-related record."""
        template_processor: Jinja2Templates = request.state.templates
        user = get_user(request.session.get("user", {}))
        session_maker = request.state.session_maker
        survey_related_record_id = get_id_from_request_path(
            request, "survey_related_record_id", schemas.SurveyRelatedRecordId
        )
        async with session_maker() as session:
            if (
                survey_related_record := await operations.get_survey_related_record(
                    survey_related_record_id, user, session, request.state.settings
                )
            ) is None:
                raise HTTPException(
                    404,
                    f"Survey-related record {survey_related_record_id!r} not found.",
                )

        parent_survey_mission_id = schemas.SurveyMissionId(
            survey_related_record.survey_mission_id
        )
        form_instance = (
            await forms.SurveyRelatedRecordUpdateForm.get_validated_form_instance(
                request,
                survey_mission_id=parent_survey_mission_id,
                disregard_id=survey_related_record_id,
            )
        )
        logger.debug(f"{form_instance.has_validation_errors()=}")

        if form_instance.has_validation_errors():
            logger.debug("form did not validate")
            logger.debug(f"{form_instance.errors=}")

            async def stream_validation_failed_events():
                template = template_processor.get_template(
                    "survey-related-records/update-form.html"
                )
                rendered = template.render(
                    request=request,
                    survey_related_record=survey_related_record,
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(stream_validation_failed_events(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_update = schemas.SurveyRelatedRecordUpdate(
            owner=user.id,
            survey_mission_id=parent_survey_mission_id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            dataset_category_id=form_instance.dataset_category_id.data,
            domain_type_id=form_instance.domain_type_id.data,
            workflow_stage_id=form_instance.workflow_stage_id.data,
            relative_path=form_instance.relative_path.data,
            bbox_4326=(
                f"POLYGON(("
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.min_lat.data}, "
                f"{form_instance.bounding_box.max_lon.data} {form_instance.bounding_box.min_lat.data}, "
                f"{form_instance.bounding_box.max_lon.data} {form_instance.bounding_box.max_lat.data}, "
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.max_lat.data}, "
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.min_lat.data}"
                f"))"
            ),
            links=[
                schemas.LinkSchema(
                    url=lf.url.data,
                    media_type=lf.media_type.data,
                    relation=lf.relation.data,
                    link_description=schemas.LocalizableDraftDescription(
                        en=lf.link_description.en.data,
                        pt=lf.link_description.pt.data,
                    ),
                )
                for lf in form_instance.links.entries
            ],
            assets=[
                schemas.RecordAssetUpdate(
                    id=schemas.RecordAssetId(uuid.UUID(af.asset_id.data)),
                    name=schemas.LocalizableDraftName(
                        en=af.asset_name.en.data,
                        pt=af.asset_name.pt.data,
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en=af.asset_description.en.data,
                        pt=af.asset_description.pt.data,
                    ),
                    relative_path=af.relative_path.data,
                    links=[
                        schemas.LinkSchema(
                            url=afl.url.data,
                            media_type=afl.media_type.data,
                            relation=afl.relation.data,
                            link_description=schemas.LocalizableDraftDescription(
                                en=afl.link_description.en.data,
                                pt=afl.link_description.pt.data,
                            ),
                        )
                        for afl in af.asset_links.entries
                    ],
                )
                for af in form_instance.assets.entries
            ],
        )

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            """Handle successful processing of the survey-related record update background task.

            After receiving the final message with a success status, update the
            UI to reflect the changes.
            """
            details = await _get_survey_related_record_details(request)
            rendered_message = message_template.render(
                status=final_message.status.value,
                message=final_message.message,
            )
            yield ServerSentEventGenerator.patch_elements(
                rendered_message,
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            template = template_processor.get_template(
                "survey-related-records/detail-component.html"
            )
            # need to update:
            # - survey-related record details section (name, description, links, ...)
            # - breadcrumbs (record's name may have changed)
            # - page title (record's name may have changed)
            # - clear the feedback section
            breadcrumbs_template = template_processor.get_template("breadcrumbs.html")
            yield ServerSentEventGenerator.patch_elements(
                breadcrumbs_template.render(
                    request=request, breadcrumbs=details.breadcrumbs
                ),
                selector=schemas.selector_info.breadcrumbs_selector,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                template.render(
                    request=request,
                    survey_related_record=details.item,
                    permissions=details.permissions,
                ),
                selector=schemas.selector_info.main_content_selector,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                details.item.name.en,
                selector=schemas.selector_info.page_title_selector,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                "",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.INNER,
            )

        async def handle_processing_failure(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            rendered = message_template.render(
                status=final_message.status.value,
                message=f"ERROR: {final_message.message}",
            )
            yield ServerSentEventGenerator.patch_elements(
                rendered,
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

        async def event_streamer():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Updating survey-related record as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.update_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_survey_related_record_id=str(survey_related_record_id),
                raw_to_update=to_update.model_dump_json(exclude_unset=True),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=f"progress:{request_id}",
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                patch_elements_selector=schemas.selector_info.feedback_selector,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(event_streamer(), status_code=202)


routes = [
    Route(
        "/{survey_mission_id}/new",
        get_creation_form,
        methods=["GET"],
        name="get_creation_form",
    ),
    Route(
        "/{survey_mission_id}/new/add-form-link",
        add_creation_form_link,
        methods=["POST"],
        name="add_form_link",
    ),
    Route(
        "/{survey_mission_id}/new/remove-form-link",
        remove_creation_form_link,
        methods=["POST"],
        name="remove_form_link",
    ),
    Route(
        "/{survey_mission_id}/new/add-asset-form",
        add_creation_form_asset,
        methods=["POST"],
        name="add_asset_form",
    ),
    Route(
        "/{survey_mission_id}/new/remove-asset-form",
        remove_creation_form_asset,
        methods=["POST"],
        name="remove_asset_form",
    ),
    Route(
        "/{survey_mission_id}/new/add-asset-link-form/{asset_index}",
        add_creation_form_asset_link,
        methods=["POST"],
        name="add_asset_link_form",
    ),
    Route(
        "/{survey_mission_id}/new/remove-asset-link-form/{asset_index}",
        remove_creation_form_asset_link,
        methods=["POST"],
        name="remove_asset_link_form",
    ),
    Route(
        "/",
        SurveyRelatedRecordCollectionEndpoint,
        methods=["GET"],
        name="list",
    ),
    Route(
        "/search",
        get_list_component,
        methods=["GET"],
        name="get_list_component",
    ),
    Route(
        "/{survey_related_record_id}",
        SurveyRelatedRecordDetailEndpoint,
        name="detail",
    ),
    Route(
        "/{survey_related_record_id}/details",
        get_details_component,
        methods=["GET"],
        name="get_details_component",
    ),
    Route(
        "/{survey_related_record_id}/update",
        get_update_form,
        methods=["GET"],
        name="get_update_form",
    ),
    Route(
        "/{survey_related_record_id}/update/add-form-link",
        add_update_form_link,
        methods=["POST"],
        name="add_update_form_link",
    ),
    Route(
        "/{survey_related_record_id}/update/remove-form-link",
        remove_update_form_link,
        methods=["POST"],
        name="remove_update_form_link",
    ),
    Route(
        "/{survey_related_record_id}/update/add-asset-form",
        add_update_form_asset,
        methods=["POST"],
        name="add_update_form_asset",
    ),
    Route(
        "/{survey_related_record_id}/update/remove-asset-form",
        remove_update_form_asset,
        methods=["POST"],
        name="remove_update_form_asset",
    ),
    Route(
        "/{survey_related_record_id}/update/add-asset-link-form/{asset_index}",
        add_update_form_asset_link,
        methods=["POST"],
        name="add_update_form_asset_link",
    ),
    Route(
        "/{survey_related_record_id}/update/remove-asset-link-form/{asset_index}",
        remove_update_form_asset_link,
        methods=["POST"],
        name="remove_update_form_asset_link",
    ),
]
