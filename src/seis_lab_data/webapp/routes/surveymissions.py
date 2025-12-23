import asyncio
import dataclasses
import json
import logging
import uuid
from typing import AsyncGenerator

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
    geojson,
    operations,
    permissions,
    schemas,
)
from ...constants import (
    PROGRESS_TOPIC_NAME_TEMPLATE,
    SURVEY_MISSION_DELETED_TOPIC,
    SURVEY_MISSION_STATUS_CHANGED_TOPIC,
    SURVEY_MISSION_UPDATED_TOPIC,
    SURVEY_MISSION_VALIDITY_CHANGED_TOPIC,
)
from ...processing import tasks
from .. import (
    filters,
    forms,
)
from .auth import (
    requires_auth,
    get_user,
)
from .common import (
    get_id_from_request_path,
    get_page_from_request_params,
    get_pagination_info,
    produce_event_stream_for_item_updates,
    produce_event_stream_for_topic,
    UPDATE_BASEMAP_JS_SCRIPT,
)

logger = logging.getLogger(__name__)


async def _get_survey_mission_details(request: Request) -> schemas.SurveyMissionDetails:
    """utility function to get survey mission details and its survey-related records."""
    records_current_page = get_page_from_request_params(request)
    current_language = request.state.language
    survey_related_records_list_filters = (
        filters.SurveyRelatedRecordListFilters.from_params(
            request.query_params, current_language
        )
    )
    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    session_maker = request.state.session_maker
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    async with session_maker() as session:
        try:
            survey_mission = await operations.get_survey_mission(
                survey_mission_id,
                user.id if user else None,
                session,
                request.state.settings,
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
        ) = await operations.list_survey_related_records(
            session,
            user,
            survey_mission_id=survey_mission_id,
            include_total=True,
            page=records_current_page,
            page_size=settings.pagination_page_size,
            **survey_related_records_list_filters.as_kwargs(),
        )
    return schemas.SurveyMissionDetails(
        item=schemas.SurveyMissionReadDetail.from_db_instance(survey_mission),
        children=[
            schemas.SurveyRelatedRecordReadListItem.from_db_instance(srr)
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
        permissions=schemas.UserPermissionDetails(
            can_create_children=await permissions.can_create_survey_related_record(
                user, survey_mission_id, settings=settings
            ),
            can_update=await permissions.can_update_survey_mission(
                user, survey_mission_id, settings=settings
            ),
            can_delete=await permissions.can_delete_survey_mission(
                user, survey_mission_id, settings=settings
            ),
        ),
        breadcrumbs=[
            schemas.BreadcrumbItem(name=_("Home"), url=str(request.url_for("home"))),
            schemas.BreadcrumbItem(
                name=_("Projects"), url=str(request.url_for("projects:list"))
            ),
            schemas.BreadcrumbItem(
                name=str(survey_mission.project.name["en"]),
                url=str(
                    request.url_for(
                        "projects:detail",
                        project_id=survey_mission.project.id,
                    )
                ),
            ),
            schemas.BreadcrumbItem(
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
        permissions=details.permissions,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


async def get_survey_mission_detail_updates(request: Request):
    try:
        survey_mission_id = schemas.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
        )
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail="Invalid survey_mission id"
        ) from err
    session_maker = request.state.session_maker
    settings: config.SeisLabDataSettings = request.state.settings
    redis_client: Redis = request.state.redis_client
    user = get_user(request.session.get("user", {}))

    async def on_deleted_message(
        raw_message: str,
    ) -> AsyncGenerator[DatastarEvent, None]:
        message = schemas.SurveyMissionEvent(**json.loads(raw_message))
        deleted_id = message.survey_mission_id
        if deleted_id == survey_mission_id:
            logger.debug(
                "Received message about recent survey_mission deletion, "
                "redirecting frontend..."
            )
            yield ServerSentEventGenerator.patch_elements(
                "Survey mission has been deleted",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.INNER,
            )
            await asyncio.sleep(1)
            yield ServerSentEventGenerator.redirect(
                str(request.url_for("survey_missions:list"))
            )

    async def on_status_update_message(
        raw_message: str,
    ) -> AsyncGenerator[DatastarEvent, None]:
        message = schemas.SurveyMissionEvent(**json.loads(raw_message))
        if message.survey_mission_id == survey_mission_id:
            logger.debug(
                "Received message about recent survey_mission status update, "
                "patching frontend..."
            )
            async with session_maker() as session:
                updated_survey_mission = await operations.get_survey_mission(
                    survey_mission_id, user or None, session, settings
                )
                yield ServerSentEventGenerator.patch_signals(
                    {
                        "status": updated_survey_mission.status.value,
                    },
                )

    async def on_validation_update_message(
        raw_message: str,
    ) -> AsyncGenerator[DatastarEvent, None]:
        message = schemas.SurveyMissionEvent(**json.loads(raw_message))
        if message.survey_mission_id == survey_mission_id:
            logger.debug(
                "Received message about recent survey_mission validation update, "
                "patching frontend..."
            )
            async with session_maker() as session:
                updated_survey_mission = await operations.get_survey_mission(
                    survey_mission_id, user or None, session, settings
                )
                details_message = ""
                if not updated_survey_mission.validation_result.get("is_valid"):
                    details_message += "<ul>"
                    for err in updated_survey_mission.validation_result.get(
                        "errors", []
                    ):
                        detail = f"{err['name']}: {err['message']}"
                        details_message += f"<li>{detail}</li>"
                yield ServerSentEventGenerator.patch_elements(
                    details_message,
                    selector=schemas.selector_info.validation_result_details_selector,
                    mode=ElementPatchMode.INNER,
                )
                yield ServerSentEventGenerator.patch_signals(
                    {
                        "isValid": updated_survey_mission.validation_result["is_valid"],
                    },
                )

    async def on_update_message(
        raw_message: str,
    ) -> AsyncGenerator[DatastarEvent, None]:
        message = schemas.SurveyMissionEvent(**json.loads(raw_message))
        if message.survey_mission_id == survey_mission_id:
            logger.debug("Received message about recent survey_mission update")
            yield ServerSentEventGenerator.patch_elements(
                "Survey mission has been updated - refreshing the page shortly",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.INNER,
            )
            await asyncio.sleep(1)
            yield ServerSentEventGenerator.redirect(
                str(
                    request.url_for(
                        "survey_missions:detail", survey_mission_id=survey_mission_id
                    )
                ),
            )

    topic_handlers = {
        SURVEY_MISSION_DELETED_TOPIC.format(
            survey_mission_id=survey_mission_id
        ): on_deleted_message,
        SURVEY_MISSION_VALIDITY_CHANGED_TOPIC.format(
            survey_mission_id=survey_mission_id
        ): on_validation_update_message,
        SURVEY_MISSION_STATUS_CHANGED_TOPIC.format(
            survey_mission_id=survey_mission_id
        ): on_status_update_message,
        SURVEY_MISSION_UPDATED_TOPIC.format(
            survey_mission_id=survey_mission_id
        ): on_update_message,
    }

    async def event_streamer():
        async for sse_event in produce_event_stream_for_item_updates(
            redis_client, request, timeout_seconds=30, **topic_handlers
        ):
            yield sse_event

    return DatastarResponse(event_streamer())


@csrf_protect
@requires_auth
async def get_survey_mission_creation_form(request: Request):
    user = get_user(request.session.get("user", {}))
    project_id = schemas.ProjectId(uuid.UUID(request.path_params["project_id"]))
    session_maker = request.state.session_maker
    form_instance = await forms.SurveyMissionCreateForm.from_formdata(request)

    async with session_maker() as session:
        try:
            project = await operations.get_project(
                project_id, user, session, request.state.settings
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(
                status_code=404, detail=_(f"Project {project_id!r} not found.")
            )

    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/create-form.html")
    rendered = template.render(
        request=request,
        project=schemas.ProjectReadDetail.from_db_instance(project),
        form=form_instance,
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
                name=project.name["en"],
                url=str(request.url_for("projects:detail", project_id=project.id)),
            ),
            schemas.BreadcrumbItem(
                name=_("New Survey mission"),
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
            _("new survey mission"),
            selector=schemas.selector_info.page_title_selector,
            mode=ElementPatchMode.INNER,
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
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    async with session_maker() as session:
        items, num_total = await operations.list_survey_missions(
            session,
            initiator=user.id if user else None,
            page=current_page,
            page_size=settings.pagination_page_size,
            include_total=True,
            **internal_filter_kwargs,
        )
        num_unfiltered_total = (
            await operations.list_survey_missions(
                session, initiator=user or None, include_total=True
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
        schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
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
            selector=schemas.selector_info.items_selector,
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


class SurveyMissionCollectionEndpoint(HTTPEndpoint):
    """Manage collection of survey missions."""

    async def get(self, request: Request):
        """List survey missions."""
        current_page = get_page_from_request_params(request)
        current_language = request.state.language
        list_filters = filters.SurveyMissionListFilters.from_params(
            request.query_params, current_language
        )
        session_maker = request.state.session_maker
        settings: config.SeisLabDataSettings = request.state.settings
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            items, num_total = await operations.list_survey_missions(
                session,
                initiator=user.id if user else None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
                **list_filters.as_kwargs(),
            )
            num_unfiltered_total = (
                await operations.list_survey_missions(
                    session, initiator=user or None, include_total=True
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
            schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
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
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Survey Missions")),
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
        user = get_user(request.session.get("user", {}))
        session_maker = request.state.session_maker
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", schemas.SurveyMissionId
        )
        async with session_maker() as session:
            if (
                survey_mission := await operations.get_survey_mission(
                    survey_mission_id, user, session, request.state.settings
                )
            ) is None:
                raise HTTPException(
                    404, f"Survey mission {survey_mission_id!r} not found."
                )
        form_instance = await forms.SurveyMissionUpdateForm.get_validated_form_instance(
            request,
            project_id=schemas.ProjectId(survey_mission.project_id),
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
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(stream_validation_failed_events(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_update = schemas.SurveyMissionUpdate(
            owner=user.id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
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
        )

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            """Handle successful processing of the project update background task.

            After receiving the final message with a success status, update the
            UI to reflect the changes.
            """
            details = await _get_survey_mission_details(request)
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
                "survey-missions/detail-component.html"
            )
            # need to update:
            # - project details section (name, description, links, ...)
            # - breadcrumbs (project name may have changed)
            # - page title (project name may have changed)
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
                    survey_mission=details.item,
                    pagination=details.pagination,
                    items=details.children,
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

            tasks.validate_survey_mission.send(
                raw_request_id=str(request_id),
                raw_survey_mission_id=str(survey_mission_id),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
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
                """<li>Updating survey mission as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.update_survey_mission.send(
                raw_request_id=str(request_id),
                raw_survey_mission_id=str(survey_mission_id),
                raw_to_update=to_update.model_dump_json(exclude_unset=True),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id),
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                patch_elements_selector=schemas.selector_info.feedback_selector,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(event_streamer(), status_code=202)

    @csrf_protect
    @requires_auth
    async def post(self, request: Request):
        """Create a new record in the survey mission's collection."""
        user = get_user(request.session.get("user", {}))
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", schemas.SurveyMissionId
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
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(event_streamer(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        related_records = []
        for related_ in form_instance.related_records.entries:
            related_records.append(
                schemas.RelatedRecordCreate(
                    related_record_id=schemas.SurveyRelatedRecordId(
                        uuid.UUID(
                            form_instance.parse_related_record_compound_name(
                                related_.related_record.data
                            )
                        )
                    ),
                    relationship=schemas.LocalizableDraftRelationship(
                        en=related_.relationship.en.data,
                        pt=related_.relationship.pt.data,
                    ),
                )
            )
        to_create = schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(uuid.uuid4()),
            survey_mission_id=survey_mission_id,
            owner=user.id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            relative_path=form_instance.relative_path.data,
            dataset_category_id=form_instance.dataset_category_id.data,
            domain_type_id=form_instance.domain_type_id.data,
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
                schemas.RecordAssetCreate(
                    id=schemas.RecordAssetId(uuid.uuid4()),
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
            related_records=related_records,
        )
        logger.info(f"{to_create=}")

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            """Handle successful processing of the survey-related record creation background task."""

            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    data_test_id="processing-success-message",
                    status=final_message.status.value,
                    message=final_message.message,
                ),
                selector=schemas.selector_info.main_content_selector,
                mode=ElementPatchMode.APPEND,
            )
            await asyncio.sleep(1)

            tasks.validate_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_survey_related_record_id=str(to_create.id),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            yield ServerSentEventGenerator.redirect(
                str(
                    request.url_for(
                        "survey_related_records:detail",
                        survey_related_record_id=to_create.id,
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
                """<li>Creating survey-related record as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.create_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_to_create=to_create.model_dump_json(),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id),
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                patch_elements_selector=schemas.selector_info.feedback_selector,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events(), status_code=202)

    @csrf_protect
    @requires_auth
    async def delete(self, request: Request):
        survey_mission_id = get_id_from_request_path(
            request, "survey_mission_id", schemas.SurveyMissionId
        )
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            try:
                survey_mission = await operations.get_survey_mission(
                    survey_mission_id,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if survey_mission is None:
                raise HTTPException(
                    status_code=404,
                    detail=_(f"Survey mission {survey_mission_id!r} not found."),
                )

        request_id = schemas.RequestId(uuid.uuid4())

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
                        "projects:detail", project_id=survey_mission.project_id
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
                """<li>Deleting survey mission as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            enqueued_message: Message = tasks.delete_survey_mission.send(
                raw_request_id=str(request_id),
                raw_survey_mission_id=str(survey_mission_id),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id),
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                patch_elements_selector=schemas.selector_info.feedback_selector,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())


@csrf_protect
async def add_create_survey_mission_form_link(request: Request):
    """Add a form link to a create_survey_mission form."""
    user = get_user(request.session.get("user", {}))
    session_maker = request.state.session_maker
    project_id = schemas.ProjectId(uuid.UUID(request.path_params["project_id"]))
    async with session_maker() as session:
        try:
            project = await operations.get_project(
                project_id,
                user or None,
                session,
                request.state.settings,
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
        project=schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_mission_form_link(request: Request):
    """Remove a form link from a create_survey_mission form."""
    user = get_user(request.session.get("user", {}))
    session_maker = request.state.session_maker
    project_id = schemas.ProjectId(uuid.UUID(request.path_params["project_id"]))
    async with session_maker() as session:
        try:
            project = await operations.get_project(
                project_id,
                user or None,
                session,
                request.state.settings,
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
        project=schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
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
            selector=schemas.selector_info.main_content_selector,
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
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
@requires_auth
async def get_survey_mission_update_form(request: Request):
    """Return a form suitable for updating an existing survey mission."""
    user = get_user(request.session.get("user", {}))
    session_maker = request.state.session_maker
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    async with session_maker() as session:
        try:
            survey_mission = await operations.get_survey_mission(
                survey_mission_id,
                user or None,
                session,
                request.state.settings,
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
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/update-form.html")
    rendered = template.render(
        request=request,
        survey_mission=survey_mission,
        form=update_form,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

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
        "/{project_id}/new",
        get_survey_mission_creation_form,
        methods=["GET"],
        name="get_creation_form",
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
        "/{survey_mission_id}/detail-updates",
        get_survey_mission_detail_updates,
        methods=["GET"],
        name="get_detail_updates",
    ),
    Route(
        "/{survey_mission_id}/update",
        get_survey_mission_update_form,
        methods=["GET"],
        name="get_update_form",
    ),
    Route(
        "/{survey_mission_id}",
        SurveyMissionDetailEndpoint,
        name="detail",
    ),
]
