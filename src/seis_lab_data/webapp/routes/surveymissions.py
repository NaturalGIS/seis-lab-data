import dataclasses
import json
import logging
import uuid

import shapely
from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
from redis.asyncio import Redis
from starlette_babel import gettext_lazy as _
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette_wtf import csrf_protect

from ... import (
    config,
    constants,
    errors,
    geojson,
    subscribers,
)
from ...operations import (
    projects as project_ops,
    surveymissions as survey_mission_ops,
    surveyrelatedrecords as survey_related_record_ops,
)
from ...permissions import (
    surveymissions as mission_permissions,
    surveyrelatedrecords as record_permissions,
)
from ...tasks import (
    discovery as discovery_tasks,
    surveymissions as mission_tasks,
    surveyrelatedrecords as record_tasks,
)
from ...schemas import (
    common as common_schemas,
    identifiers,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
    webui as webui_schemas,
)
from .. import (
    filters,
    forms,
)
from ..streamhandlers import common as common_handlers
from .auth import (
    requires_auth,
)
from .common import (
    get_id_from_request_path,
    get_page_from_request_params,
    get_pagination_info,
    UPDATE_BASEMAP_JS_SCRIPT,
)

logger = logging.getLogger(__name__)


async def _get_survey_mission_details(
    request: Request,
) -> webui_schemas.SurveyMissionDetails:
    """utility function to get survey mission details and its survey-related records."""
    records_current_page = get_page_from_request_params(request)
    current_language = request.state.language
    survey_related_records_list_filters = (
        filters.SurveyRelatedRecordListFilters.from_params(
            request.query_params, current_language
        )
    )
    user = request.user if request.user.is_authenticated else None
    settings: config.SeisLabDataSettings = request.state.settings
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", identifiers.SurveyMissionId
    )
    async with settings.get_db_session_maker()() as session:
        try:
            survey_mission = await survey_mission_ops.get_survey_mission(
                survey_mission_id,
                user,
                session,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_mission is None:
            raise HTTPException(
                status_code=404,
                detail=_(f"Survey mission {survey_mission_id!r} not found."),
            )
        (
            survey_related_records,
            total,
        ) = await survey_related_record_ops.list_survey_related_records(
            session,
            user,
            survey_mission_id=survey_mission_id,
            include_total=True,
            page=records_current_page,
            page_size=settings.pagination_page_size,
            **survey_related_records_list_filters.as_kwargs(),
        )
    return webui_schemas.SurveyMissionDetails(
        item=webui_schemas.SurveyMissionReadDetail.from_db_instance(survey_mission),
        children=[
            webui_schemas.SurveyRelatedRecordReadListItem.from_db_instance(srr)
            for srr in survey_related_records
        ],
        children_filter=survey_related_records_list_filters.get_text_search_filter(
            current_language
        ),
        pagination=get_pagination_info(
            records_current_page,
            request.state.settings.pagination_page_size,
            total,
            total,
            collection_url=str(
                request.url_for(
                    "survey_missions:detail", survey_mission_id=survey_mission_id
                )
            ),
        ),
        permissions=webui_schemas.UserPermissionDetails(
            can_create_children=record_permissions.can_create_survey_related_record(
                user, survey_mission
            )
            if user
            else False,
            can_update=mission_permissions.can_update_survey_mission(
                user, survey_mission
            )
            if user
            else False,
            can_delete=mission_permissions.can_delete_survey_mission(
                user, survey_mission
            )
            if user
            else False,
            can_validate=mission_permissions.can_validate_survey_mission(
                user, survey_mission
            )
            if user
            else False,
            can_discover=mission_permissions.can_discover_survey_mission(
                user, survey_mission
            )
            if user
            else False,
        ),
        breadcrumbs=[
            webui_schemas.BreadcrumbItem(
                name=_("Home"), url=str(request.url_for("home"))
            ),
            webui_schemas.BreadcrumbItem(
                name=_("Projects"), url=str(request.url_for("projects:list"))
            ),
            webui_schemas.BreadcrumbItem(
                name=str(survey_mission.project.name["en"]),
                url=str(
                    request.url_for(
                        "projects:detail",
                        project_id=survey_mission.project.id,
                    )
                ),
            ),
            webui_schemas.BreadcrumbItem(
                name=str(survey_mission.name["en"]),
            ),
        ],
    )


@requires_auth
async def get_details_component(request: Request):
    details = await _get_survey_mission_details(request)
    template_processor = request.state.templates
    template = template_processor.get_template("survey-missions/detail-component.html")
    rendered = template.render(
        request=request,
        survey_mission=details.item,
        pagination=details.pagination,
        survey_related_records=details.children,
        search_initial_value=details.children_filter,
        permissions=details.permissions,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@requires_auth
async def stream_to_update_page(request: Request):
    try:
        survey_mission_id = identifiers.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
        )
        request_id = identifiers.RequestId(uuid.UUID(request.path_params["request_id"]))
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail="Invalid survey_mission id"
        ) from err
    session_maker = request.state.settings.get_db_session_maker()
    redis_client: Redis = request.state.redis_client
    user = request.user if request.user.is_authenticated else None

    subscription = subscribers.subscribe_to_topic(
        redis_client,
        [constants.NEW_TOPIC_SURVEY_MISSIONS],
        subscribers.HandlerContext(
            resource_id=str(survey_mission_id),
            resource_type=constants.ResourceType.MISSION,
            user=user,
            jinja_environment=request.state.templates.env,
            url_resolver=request.url_for,
            db_session_factory=session_maker,
            request_id=request_id,
        ),
        message_handlers={
            "resource_modified": common_handlers.handle_resource_modification_edit_page,
        },
    )

    async def event_streamer():
        async for datastar_event in subscription:
            yield datastar_event

    return DatastarResponse(event_streamer())


async def stream_to_detail_page(request: Request):
    try:
        survey_mission_id = identifiers.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
        )
        request_id = identifiers.RequestId(uuid.UUID(request.path_params["request_id"]))
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail="Invalid survey_mission id"
        ) from err
    session_maker = request.state.settings.get_db_session_maker()
    redis_client: Redis = request.state.redis_client
    user = request.user if request.user.is_authenticated else None

    subscription = subscribers.subscribe_to_topic(
        redis_client,
        [
            constants.NEW_TOPIC_SURVEY_MISSIONS,
            constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
        ],
        subscribers.HandlerContext(
            resource_id=str(survey_mission_id),
            user=user,
            jinja_environment=request.state.templates.env,
            url_resolver=request.url_for,
            db_session_factory=session_maker,
            request_id=request_id,
            resource_type=constants.ResourceType.MISSION,
            target_page=constants.PageType.RESOURCE_DETAIL,
        ),
        message_handlers={
            "resource_modified": common_handlers.handle_resource_modification_detail_page,
            "discovery": common_handlers.handle_discovery_detail_page,
        },
    )

    async def event_streamer():
        async for datastar_event in subscription:
            yield datastar_event

    return DatastarResponse(event_streamer())


@csrf_protect
@requires_auth
async def get_survey_mission_creation_form(request: Request):
    user = request.user if request.user.is_authenticated else None
    project_id = identifiers.ProjectId(uuid.UUID(request.path_params["project_id"]))
    form_instance = await forms.SurveyMissionCreateForm.from_formdata(request)
    form_instance.request_id.data = str(identifiers.RequestId(uuid.uuid4()))

    async with request.state.settings.get_db_session_maker()() as session:
        try:
            project = await project_ops.get_project(project_id, user, session)
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(
                status_code=404, detail=_(f"Project {project_id!r} not found.")
            )

    template_processor: Jinja2Templates = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-missions/create-form-page.html",
        context={
            "project": webui_schemas.ProjectReadDetail.from_db_instance(project),
            "form": form_instance,
            "breadcrumbs": [
                webui_schemas.BreadcrumbItem(
                    name=_("Home"), url=request.url_for("home")
                ),
                webui_schemas.BreadcrumbItem(
                    name=_("Projects"), url=request.url_for("projects:list")
                ),
                webui_schemas.BreadcrumbItem(
                    name=project.name["en"],
                    url=request.url_for("projects:detail", project_id=project.id),
                ),
                webui_schemas.BreadcrumbItem(name=_("New survey mission")),
            ],
        },
    )


async def get_mission_records_list_component(request: Request):
    """Return a paginated, filtered list of records belonging to a survey mission."""
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", identifiers.SurveyMissionId
    )
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
    current_page = get_page_from_request_params(request)
    settings: config.SeisLabDataSettings = request.state.settings
    user = request.user if request.user.is_authenticated else None
    async with settings.get_db_session_maker()() as session:
        items, num_total = await survey_related_record_ops.list_survey_related_records(
            session,
            initiator=user,
            survey_mission_id=survey_mission_id,
            page=current_page,
            page_size=settings.pagination_page_size,
            include_total=True,
            **internal_filter_kwargs,
        )
        num_unfiltered_total = (
            await survey_related_record_ops.list_survey_related_records(
                session,
                initiator=user,
                survey_mission_id=survey_mission_id,
                include_total=True,
            )
        )[1]
    pagination_info = get_pagination_info(
        current_page,
        settings.pagination_page_size,
        num_total,
        num_unfiltered_total,
        collection_url=str(
            request.url_for(
                "survey_missions:detail", survey_mission_id=survey_mission_id
            )
        ),
    )
    serialized_items = [
        webui_schemas.SurveyRelatedRecordReadListItem.from_db_instance(i) for i in items
    ]
    template_processor = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/list-component.html"
    )
    rendered = template.render(
        request=request,
        items=serialized_items,
        update_current_url_with=filter_query_string,
        pagination=pagination_info,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.items_selector,
            mode=ElementPatchMode.REPLACE,
        )

    return DatastarResponse(event_streamer())


async def get_list_component(request: Request):
    if (raw_search_params := request.query_params.get("datastar")) is not None:
        try:
            list_filters = filters.SurveyMissionListFilters.from_json(
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

    current_page = get_page_from_request_params(request)
    settings: config.SeisLabDataSettings = request.state.settings
    user = request.user if request.user.is_authenticated else None
    async with settings.get_db_session_maker()() as session:
        items, num_total = await survey_mission_ops.list_survey_missions(
            session,
            initiator=user,
            page=current_page,
            page_size=settings.pagination_page_size,
            include_total=True,
            **internal_filter_kwargs,
        )
        num_unfiltered_total = (
            await survey_mission_ops.list_survey_missions(
                session, initiator=user, include_total=True
            )
        )[1]

    pagination_info = get_pagination_info(
        current_page,
        settings.pagination_page_size,
        num_total,
        num_unfiltered_total,
        collection_url=str(request.url_for("survey_missions:list")),
    )
    serialized_items = [
        webui_schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
    ]
    template_processor = request.state.templates
    template = template_processor.get_template("survey-missions/list-component.html")
    rendered = template.render(
        request=request,
        items=serialized_items,
        update_current_url_with=filter_query_string,
        pagination=pagination_info,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.items_selector,
            mode=ElementPatchMode.REPLACE,
        )
        yield ServerSentEventGenerator.execute_script(
            UPDATE_BASEMAP_JS_SCRIPT.format(
                dumped_features=json.dumps(
                    geojson.to_feature_collection(serialized_items)
                )
            )
        )

    return DatastarResponse(event_streamer())


async def stream_to_list_page(request: Request):
    subscription = subscribers.subscribe_to_topic(
        request.state.redis_client,
        [constants.NEW_TOPIC_SURVEY_MISSIONS],
        subscribers.HandlerContext(
            resource_type=constants.ResourceType.MISSION,
            jinja_environment=request.state.templates.env,
            url_resolver=request.url_for,
            db_session_factory=request.state.settings.get_db_session_maker(),
            user=request.user if request.user.is_authenticated else None,
        ),
        {
            "resource_modified": common_handlers.handle_resource_modification_list_page,
        },
    )

    async def event_streamer():
        async for sse_event in subscription:
            yield sse_event

    return DatastarResponse(event_streamer(), status_code=200)


class SurveyMissionCollectionEndpoint(HTTPEndpoint):
    """Manage collection of survey missions."""

    async def get(self, request: Request):
        """List survey missions."""
        current_page = get_page_from_request_params(request)
        current_language = request.state.language
        list_filters = filters.SurveyMissionListFilters.from_params(
            request.query_params, current_language
        )
        settings: config.SeisLabDataSettings = request.state.settings
        user = request.user if request.user.is_authenticated else None
        async with settings.get_db_session_maker()() as session:
            items, num_total = await survey_mission_ops.list_survey_missions(
                session,
                initiator=user,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
                **list_filters.as_kwargs(),
            )
            num_unfiltered_total = (
                await survey_mission_ops.list_survey_missions(
                    session, initiator=user, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page,
            settings.pagination_page_size,
            num_total,
            num_unfiltered_total,
            collection_url=str(request.url_for("survey_missions:list")),
        )
        if (current_bbox := list_filters.spatial_intersect_filter) is not None:
            min_lon, min_lat, max_lon, max_lat = current_bbox.value.bounds
        else:
            default_bbox = shapely.from_wkt(settings.webmap_default_bbox_wkt)
            min_lon, min_lat, max_lon, max_lat = default_bbox.bounds
        serialized_items = [
            webui_schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
        ]
        geojson_features = geojson.to_feature_collection(serialized_items)
        return template_processor.TemplateResponse(
            request,
            "survey-missions/list.html",
            context={
                "items": serialized_items,
                "geojson_features": json.dumps(geojson_features),
                "pagination": pagination_info,
                "map_bounds": {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                },
                "current_temporal_extent": {
                    "begin": settings.default_temporal_extent_begin,
                    "end": settings.default_temporal_extent_end,
                },
                "breadcrumbs": [
                    webui_schemas.BreadcrumbItem(
                        name=_("Home"), url=request.url_for("home")
                    ),
                    webui_schemas.BreadcrumbItem(name=_("Survey Missions")),
                ],
                "search_initial_value": list_filters.get_text_search_filter(
                    current_language
                ),
                "map_popup_detail_base_url": str(
                    request.url_for("survey_missions:detail", survey_mission_id="_")
                ).rpartition("/")[0],
            },
        )


class SurveyMissionDetailEndpoint(HTTPEndpoint):
    """Survey mission detail endpoint."""

    async def get(self, request: Request):
        details = await _get_survey_mission_details(request)
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "survey-missions/detail.html",
            context={
                "request_id": uuid.uuid4(),
                "survey_mission": details.item,
                "pagination": details.pagination,
                "survey_related_records": details.children,
                "search_initial_value": details.children_filter,
                "permissions": details.permissions,
                "breadcrumbs": details.breadcrumbs,
            },
        )

    @csrf_protect
    @requires_auth
    async def put(self, request: Request):
        """Update an existing survey mission."""
        template_processor: Jinja2Templates = request.state.templates
        user = request.user
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", identifiers.SurveyMissionId
        )
        async with request.state.settings.get_db_session_maker()() as session:
            if (
                survey_mission := await survey_mission_ops.get_survey_mission(
                    survey_mission_id, user, session
                )
            ) is None:
                raise HTTPException(
                    404, f"Survey mission {survey_mission_id!r} not found."
                )
        form_instance = await forms.SurveyMissionUpdateForm.get_validated_form_instance(
            request,
            project_id=identifiers.ProjectId(survey_mission.project_id),
            disregard_id=survey_mission_id,
        )
        logger.debug(f"{form_instance.has_validation_errors()=}")

        if form_instance.has_validation_errors():
            logger.debug("form did not validate")
            logger.debug(f"{form_instance.errors=}")

            async def stream_validation_failed_events():
                template = template_processor.get_template(
                    "survey-missions/update-form.html"
                )
                rendered = template.render(
                    request=request,
                    survey_mission=survey_mission,
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=webui_schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )
                yield ServerSentEventGenerator.execute_script(
                    "document.querySelector('.is-invalid')?.scrollIntoView({behavior: 'smooth', block: 'center'})"
                )

            # Datastar only processes SSE streams from 2xx responses; non-2xx are treated as errors
            return DatastarResponse(stream_validation_failed_events(), status_code=200)

        to_update = mission_schemas.SurveyMissionUpdate(
            owner_id=user.id,
            name=common_schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=common_schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
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
            temporal_extent_begin=form_instance.temporal_extent_begin.data,
            temporal_extent_end=form_instance.temporal_extent_end.data,
            links=[
                common_schemas.LinkSchema(
                    url=lf.url.data,
                    media_type=lf.media_type.data,
                    relation=lf.relation.data,
                    link_description=common_schemas.LocalizableDraftDescription(
                        en=lf.link_description.en.data,
                        pt=lf.link_description.pt.data,
                    ),
                )
                for lf in form_instance.links.entries
            ],
        )

        mission_tasks.update_survey_mission.send(
            raw_request_id=str(form_instance.request_id.data),
            raw_survey_mission_id=str(survey_mission_id),
            raw_to_update=to_update.model_dump_json(exclude_unset=True),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )

        return Response(status_code=200)

    @csrf_protect
    @requires_auth
    async def post(self, request: Request):
        """Create a new record under the survey mission."""
        user = request.user
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", identifiers.SurveyMissionId
        )
        form_instance = (
            await forms.SurveyRelatedRecordCreateForm.get_validated_form_instance(
                request, survey_mission_id
            )
        )
        template_processor: Jinja2Templates = request.state.templates

        if form_instance.has_validation_errors():
            logger.debug("form did not validate")
            template = template_processor.get_template(
                "survey-related-records/create-form.html"
            )
            rendered = template.render(
                request=request,
                form=form_instance,
                survey_mission_id=survey_mission_id,
            )

            async def event_streamer():
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=webui_schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )
                yield ServerSentEventGenerator.execute_script(
                    "document.querySelector('.is-invalid')?.scrollIntoView({behavior: 'smooth', block: 'center'})"
                )

            # Datastar only processes SSE streams from 2xx responses; non-2xx are treated as errors
            return DatastarResponse(event_streamer(), status_code=200)

        related_records = []
        for related_ in form_instance.related_records.entries:
            related_records.append(
                record_schemas.RelatedRecordCreate(
                    related_record_id=identifiers.SurveyRelatedRecordId(
                        uuid.UUID(
                            form_instance.parse_related_record_compound_name(
                                related_.related_record.data
                            )
                        )
                    ),
                    relationship=common_schemas.LocalizableDraftRelationship(
                        en=related_.relationship.en.data,
                        pt=related_.relationship.pt.data,
                    ),
                )
            )
        to_create = record_schemas.SurveyRelatedRecordCreate(
            id=identifiers.SurveyRelatedRecordId(uuid.uuid4()),
            survey_mission_id=survey_mission_id,
            owner_id=user.id,
            name=common_schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=common_schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            dataset_category_id=form_instance.dataset_category_id.data,
            workflow_stage_id=form_instance.workflow_stage_id.data,
            bbox_4326=(
                f"POLYGON(("
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.min_lat.data}, "
                f"{form_instance.bounding_box.max_lon.data} {form_instance.bounding_box.min_lat.data}, "
                f"{form_instance.bounding_box.max_lon.data} {form_instance.bounding_box.max_lat.data}, "
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.max_lat.data}, "
                f"{form_instance.bounding_box.min_lon.data} {form_instance.bounding_box.min_lat.data}"
                f"))"
            ),
            temporal_extent_begin=form_instance.temporal_extent_begin.data,
            temporal_extent_end=form_instance.temporal_extent_end.data,
            links=[
                common_schemas.LinkSchema(
                    url=lf.url.data,
                    media_type=lf.media_type.data,
                    relation=lf.relation.data,
                    link_description=common_schemas.LocalizableDraftDescription(
                        en=lf.link_description.en.data,
                        pt=lf.link_description.pt.data,
                    ),
                )
                for lf in form_instance.links.entries
            ],
            assets=[
                record_schemas.RecordAssetCreate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=common_schemas.LocalizableDraftName(
                        en=af.asset_name.en.data,
                        pt=af.asset_name.pt.data,
                    ),
                    description=common_schemas.LocalizableDraftDescription(
                        en=af.asset_description.en.data,
                        pt=af.asset_description.pt.data,
                    ),
                    relative_path=af.relative_path.data,
                    links=[
                        common_schemas.LinkSchema(
                            url=afl.url.data,
                            media_type=afl.media_type.data,
                            relation=afl.relation.data,
                            link_description=common_schemas.LocalizableDraftDescription(
                                en=afl.link_description.en.data,
                                pt=afl.link_description.pt.data,
                            ),
                        )
                        for afl in af.asset_links.entries
                    ],
                )
                for af in form_instance.assets.entries
            ],
            related_records=related_records,
        )
        record_tasks.create_survey_related_record.send(
            raw_request_id=str(form_instance.request_id.data),
            raw_to_create=to_create.model_dump_json(),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )
        return Response(status_code=200)

    @csrf_protect
    @requires_auth
    async def delete(self, request: Request):
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", identifiers.SurveyMissionId
        )
        request_id = identifiers.RequestId(
            uuid.UUID(request.query_params["request_id"])
        )
        user = request.user
        async with request.state.settings.get_db_session_maker()() as session:
            try:
                survey_mission = await survey_mission_ops.get_survey_mission(
                    survey_mission_id,
                    user,
                    session,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if survey_mission is None:
                raise HTTPException(
                    status_code=404,
                    detail=_(f"Survey mission {survey_mission_id!r} not found."),
                )

        mission_tasks.delete_survey_mission.send(
            raw_request_id=str(request_id),
            raw_survey_mission_id=str(survey_mission_id),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )  # noqa
        return Response(status_code=200)


@csrf_protect
async def add_create_survey_mission_form_link(request: Request):
    """Add a form link to a create_survey_mission form."""
    user = request.user if request.user.is_authenticated else None
    project_id = identifiers.ProjectId(uuid.UUID(request.path_params["project_id"]))
    async with request.state.settings.get_db_session_maker()() as session:
        try:
            project = await project_ops.get_project(
                project_id,
                user,
                session,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(
                status_code=404, detail=_(f"Project {project_id!r} not found.")
            )
    creation_form = await forms.SurveyMissionCreateForm.from_formdata(request)
    creation_form.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/create-form.html")
    rendered = template.render(
        form=creation_form,
        request=request,
        project=webui_schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_mission_form_link(request: Request):
    """Remove a form link from a create_survey_mission form."""
    user = request.user if request.user.is_authenticated else None
    project_id = identifiers.ProjectId(uuid.UUID(request.path_params["project_id"]))
    async with request.state.settings.get_db_session_maker()() as session:
        try:
            project = await project_ops.get_project(
                project_id,
                user,
                session,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(
                status_code=404, detail=_(f"Project {project_id!r} not found.")
            )
    create_survey_mission_form = await forms.SurveyMissionCreateForm.from_formdata(
        request
    )
    link_index = int(request.query_params.get("link_index", 0))
    create_survey_mission_form.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/create-form.html")
    rendered = template.render(
        form=create_survey_mission_form,
        request=request,
        project=webui_schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_update_survey_mission_form_link(request: Request):
    """Add a form link to an update survey mission form."""
    details = await _get_survey_mission_details(request)
    form_ = await forms.SurveyMissionUpdateForm.from_formdata(request)
    form_.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/update-form.html")
    rendered = template.render(
        form=form_,
        survey_mission=details.item,
        request=request,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_update_survey_mission_form_link(request: Request):
    """Remove a form link from update survey mission update_project form."""
    details = await _get_survey_mission_details(request)
    form_ = await forms.SurveyMissionUpdateForm.from_formdata(request)
    link_index = int(request.query_params["link_index"])
    form_.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/update-form.html")
    rendered = template.render(
        form=form_,
        survey_mission=details.item,
        request=request,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=webui_schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
@requires_auth
async def get_survey_mission_update_form(request: Request):
    """Return a form suitable for updating an existing survey mission."""
    user = request.user if request.user.is_authenticated else None
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", identifiers.SurveyMissionId
    )
    async with request.state.settings.get_db_session_maker()() as session:
        try:
            survey_mission = await survey_mission_ops.get_survey_mission(
                survey_mission_id,
                user,
                session,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_mission is None:
            raise HTTPException(
                status_code=404,
                detail=_(f"Survey mission {survey_mission_id!r} not found."),
            )
    current_bbox = (
        shapely.from_wkb(survey_mission.bbox_4326.data)
        if survey_mission.bbox_4326 is not None
        else None
    )
    update_form = forms.SurveyMissionUpdateForm(
        request=request,
        data={
            "name": {
                "en": survey_mission.name.get("en", ""),
                "pt": survey_mission.name.get("pt", ""),
            },
            "description": {
                "en": survey_mission.description.get("en", ""),
                "pt": survey_mission.description.get("pt", ""),
            },
            "relative_path": survey_mission.relative_path,
            "bounding_box": {
                "min_lon": current_bbox.bounds[0],
                "min_lat": current_bbox.bounds[1],
                "max_lon": current_bbox.bounds[2],
                "max_lat": current_bbox.bounds[3],
            }
            if current_bbox
            else None,
            "temporal_extent_begin": survey_mission.temporal_extent_begin,
            "temporal_extent_end": survey_mission.temporal_extent_end,
            "links": [
                {
                    "url": li.get("url", ""),
                    "media_type": li.get("media_type", ""),
                    "relation": li.get("relation", ""),
                    "link_description": {
                        "en": li.get("link_description", {}).get("en", ""),
                        "pt": li.get("link_description", {}).get("pt", ""),
                    },
                }
                for li in survey_mission.links
            ],
        },
    )
    update_form.request_id.data = uuid.uuid4()
    template_processor: Jinja2Templates = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-missions/update-form-page.html",
        context={
            "survey_mission": survey_mission,
            "form": update_form,
            "breadcrumbs": [
                webui_schemas.BreadcrumbItem(
                    name=_("Home"), url=request.url_for("home")
                ),
                webui_schemas.BreadcrumbItem(
                    name=_("Survey missions"),
                    url=request.url_for("survey_missions:list"),
                ),
                webui_schemas.BreadcrumbItem(
                    name=survey_mission.name["en"],
                    url=request.url_for(
                        "survey_missions:detail", survey_mission_id=survey_mission_id
                    ),
                ),
                webui_schemas.BreadcrumbItem(name=_("Edit survey mission")),
            ],
        },
    )


@csrf_protect
@requires_auth
async def trigger_discovery(request: Request):
    discovery_tasks.discover_survey_mission_contents.send(
        raw_request_id=str(uuid.uuid4()),
        raw_survey_mission_id=request.path_params["survey_mission_id"],
        raw_initiator=json.dumps(dataclasses.asdict(request.user)),
    )  # noqa
    return Response(status_code=200)


@requires_auth
async def stream_to_new_page(request: Request):
    """Stream relevant updates for the new survey mission page."""
    try:
        request_id = identifiers.RequestId(uuid.UUID(request.path_params["request_id"]))
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid request id") from err

    subscription = subscribers.subscribe_to_topic(
        request.state.redis_client,
        [constants.NEW_TOPIC_SURVEY_MISSIONS],
        subscribers.HandlerContext(
            request_id=request_id,
            resource_type=constants.ResourceType.MISSION,
            user=request.user,
            url_resolver=request.url_for,
            jinja_environment=request.state.templates.env,
            db_session_factory=request.state.settings.get_db_session_maker(),
        ),
        {
            "resource_modified": common_handlers.handle_resource_modification_new_page,
        },
    )

    async def event_streamer():
        async for sse_event in subscription:
            yield sse_event

    return DatastarResponse(event_streamer())


routes = [
    Route(
        "/",
        SurveyMissionCollectionEndpoint,
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
        "/stream",
        stream_to_list_page,
        methods=["GET"],
        name="list_stream",
    ),
    Route(
        "/{project_id}/new",
        get_survey_mission_creation_form,
        methods=["GET"],
        name="get_creation_form",
    ),
    Route(
        "/{project_id}/new/{request_id}/stream",
        stream_to_new_page,
        methods=["GET"],
        name="new_stream",
    ),
    Route(
        "/{project_id}/new/add-form-link",
        add_create_survey_mission_form_link,
        methods=["POST"],
        name="add_form_link",
    ),
    Route(
        "/{project_id}/new/remove-form-link",
        remove_create_survey_mission_form_link,
        methods=["POST"],
        name="remove_form_link",
    ),
    Route(
        "/{survey_mission_id}/add-update-form-link",
        add_update_survey_mission_form_link,
        methods=["POST"],
        name="add_update_form_link",
    ),
    Route(
        "/{survey_mission_id}/remove-update-form-link",
        remove_update_survey_mission_form_link,
        methods=["POST"],
        name="remove_update_form_link",
    ),
    Route(
        "/{survey_mission_id}/details",
        get_details_component,
        methods=["GET"],
        name="get_details_component",
    ),
    Route(
        "/{survey_mission_id}/records",
        get_mission_records_list_component,
        methods=["GET"],
        name="get_mission_records_list_component",
    ),
    Route(
        "/{survey_mission_id}/stream/{request_id}",
        stream_to_detail_page,
        methods=["GET"],
        name="detail_stream",
    ),
    Route(
        "/{survey_mission_id}/update",
        get_survey_mission_update_form,
        methods=["GET"],
        name="get_update_form",
    ),
    Route(
        "/{survey_mission_id}/update/stream/{request_id}",
        stream_to_update_page,
        methods=["GET"],
        name="update_stream",
    ),
    Route(
        "/{survey_mission_id}/discover",
        trigger_discovery,
        methods=["POST"],
        name="trigger_discovery",
    ),
    Route(
        "/{survey_mission_id}",
        SurveyMissionDetailEndpoint,
        name="detail",
    ),
]
