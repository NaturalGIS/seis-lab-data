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
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette_babel import gettext_lazy as _
from starlette_wtf import csrf_protect

from ... import (
    config,
    errors,
    operations,
    permissions,
    schemas,
)
from ...processing import tasks
from .. import forms
from . import filters
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


@csrf_protect
@fancy_requires_auth
async def get_project_creation_form(request: Request):
    """Return a form suitable for creating a new project."""
    form_instance = await forms.ProjectCreateForm.from_formdata(request)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/create-form.html")
    rendered = template.render(
        request=request,
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
            schemas.BreadcrumbItem(name=_("New project")),
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
            _("new project"),
            selector=schemas.selector_info.page_title_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
@fancy_requires_auth
async def get_project_update_form(request: Request):
    """Return a form suitable for updating an existing project."""
    user = get_user(request.session.get("user", {}))
    session_maker = request.state.session_maker
    project_id = get_id_from_request_path(request, "project_id", schemas.ProjectId)
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
    current_bbox = (
        shapely.from_wkb(project.bbox_4326.data)
        if project.bbox_4326 is not None
        else None
    )
    update_form = forms.ProjectUpdateForm(
        request=request,
        data={
            "name": {
                "en": project.name.get("en", ""),
                "pt": project.name.get("pt", ""),
            },
            "description": {
                "en": project.description.get("en", ""),
                "pt": project.description.get("pt", ""),
            },
            "root_path": project.root_path,
            "bounding_box": {
                "min_lon": current_bbox.bounds[0],
                "min_lat": current_bbox.bounds[1],
                "max_lon": current_bbox.bounds[2],
                "max_lat": current_bbox.bounds[3],
            }
            if current_bbox
            else None,
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
                for li in project.links
            ],
        },
    )
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/update-form.html")
    rendered = template.render(
        request=request,
        project=schemas.ProjectReadDetail.from_db_instance(project),
        form=update_form,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@fancy_requires_auth
async def get_project_details_component(request: Request):
    details = await _get_project_details(request)
    template_processor = request.state.templates
    template = template_processor.get_template("projects/detail-component.html")
    rendered = template.render(
        request=request,
        project=details.item,
        pagination=details.pagination,
        survey_missions=details.children,
        permissions=details.permissions,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


async def _get_project_details(request: Request) -> schemas.ProjectDetails:
    """utility function to get project details and its survey missions."""
    survey_mission_current_page = get_page_from_request_params(request)
    current_language = request.state.language
    survey_mission_list_filters = filters.SurveyMissionListFilters.from_params(
        request.query_params, current_language
    )
    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    session_maker = request.state.session_maker
    project_id = get_id_from_request_path(request, "project_id", schemas.ProjectId)
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
        survey_missions, total = await operations.list_survey_missions(
            session,
            user,
            project_id=project_id,
            include_total=True,
            page=survey_mission_current_page,
            page_size=settings.pagination_page_size,
            **survey_mission_list_filters.as_kwargs(),
        )
    return schemas.ProjectDetails(
        item=schemas.ProjectReadDetail.from_db_instance(project),
        children=[
            schemas.SurveyMissionReadListItem.from_db_instance(sm)
            for sm in survey_missions
        ],
        children_filter=survey_mission_list_filters.get_text_search_filter(
            current_language
        ),
        pagination=get_pagination_info(
            survey_mission_current_page,
            settings.pagination_page_size,
            total,
            total,
            collection_url=str(
                request.url_for("projects:detail", project_id=project_id)
            ),
        ),
        permissions=schemas.UserPermissionDetails(
            can_delete=await permissions.can_delete_project(
                user, project_id, settings=request.state.settings
            ),
            can_update=await permissions.can_update_project(
                user, project_id, settings=request.state.settings
            ),
            can_create_children=await permissions.can_create_survey_mission(
                user, project_id=project_id, settings=request.state.settings
            ),
        ),
        breadcrumbs=[
            schemas.BreadcrumbItem(name=_("Home"), url=str(request.url_for("home"))),
            schemas.BreadcrumbItem(
                name=_("Projects"),
                url=request.url_for("projects:list"),
            ),
            schemas.BreadcrumbItem(
                name=project.name["en"],
            ),
        ],
    )


async def get_list_component(request: Request):
    if (raw_search_params := request.query_params.get("datastar")) is not None:
        try:
            list_filters = filters.ProjectListFilters.from_json(
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
        items, num_total = await operations.list_projects(
            session,
            initiator=user or None,
            page=current_page,
            page_size=settings.pagination_page_size,
            include_total=True,
            **internal_filter_kwargs,
        )
        num_unfiltered_total = (
            await operations.list_projects(
                session, initiator=user or None, include_total=True
            )
        )[1]

    pagination_info = get_pagination_info(
        current_page,
        settings.pagination_page_size,
        num_total,
        num_unfiltered_total,
        collection_url=str(request.url_for("projects:list")),
    )
    template_processor = request.state.templates
    template = template_processor.get_template("projects/list-component.html")
    rendered = template.render(
        request=request,
        items=[schemas.ProjectReadListItem.from_db_instance(i) for i in items],
        update_current_url_with=filter_query_string,
        pagination=pagination_info,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.items_selector,
            mode=ElementPatchMode.REPLACE,
        )

    return DatastarResponse(event_streamer())


class ProjectCollectionEndpoint(HTTPEndpoint):
    """Manage the collection of projects."""

    async def get(self, request: Request):
        """List projects."""
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        settings: config.SeisLabDataSettings = request.state.settings
        current_page = get_page_from_request_params(request)
        current_language = request.state.language
        list_filters = filters.ProjectListFilters.from_params(
            request.query_params, current_language
        )
        async with session_maker() as session:
            items, num_total = await operations.list_projects(
                session,
                initiator=user or None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
                **list_filters.as_kwargs(),
            )
            num_unfiltered_total = (
                await operations.list_projects(
                    session, initiator=user or None, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page,
            settings.pagination_page_size,
            num_total,
            num_unfiltered_total,
            collection_url=str(request.url_for("projects:list")),
        )
        if (current_bbox := list_filters.spatial_intersect_filter) is not None:
            min_lon, min_lat, max_lon, max_lat = current_bbox.value.bounds
        else:
            default_bbox = shapely.from_wkt(settings.webmap_default_bbox_wkt)
            min_lon, min_lat, max_lon, max_lat = default_bbox.bounds

        return template_processor.TemplateResponse(
            request,
            "projects/list.html",
            context={
                "items": [
                    schemas.ProjectReadListItem.from_db_instance(i) for i in items
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
                    schemas.BreadcrumbItem(name=_("Projects")),
                ],
                "user_can_create": await permissions.can_create_project(
                    user, request.state.settings
                ),
                "search_initial_value": list_filters.get_text_search_filter(
                    current_language
                ),
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        """Create a new project."""
        template_processor: Jinja2Templates = request.state.templates
        user = get_user(request.session.get("user", {}))
        form_instance = await forms.ProjectCreateForm.get_validated_form_instance(
            request
        )
        if form_instance.has_validation_errors():
            logger.debug("form did not validate")

            async def event_streamer():
                template = template_processor.get_template("projects/create-form.html")
                rendered = template.render(
                    request=request,
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(event_streamer(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_create = schemas.ProjectCreate(
            id=schemas.ProjectId(uuid.uuid4()),
            owner=user.id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            root_path=form_instance.root_path.data,
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
        )
        logger.info(f"{to_create=}")

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    data_test_id="processing-success-message",
                    status=final_message.status,
                    message=f"{final_message.message} - you will be redirected shortly.",
                ),
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            await asyncio.sleep(1)
            yield ServerSentEventGenerator.redirect(
                str(request.url_for("projects:detail", project_id=to_create.id)),
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
                """<li>Creating project as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.create_project.send(
                raw_request_id=str(request_id),
                raw_to_create=to_create.model_dump_json(),
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


class ProjectDetailEndpoint(HTTPEndpoint):
    """Manage a single project and its collection of survey missions."""

    async def get(self, request: Request):
        """
        Get project details and provide a paginated list of its survey missions.
        """

        details = await _get_project_details(request)
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "projects/detail.html",
            context={
                "project": details.item,
                "pagination": details.pagination,
                "survey_missions": details.children,
                "search_initial_value": details.children_filter,
                "permissions": details.permissions,
                "breadcrumbs": details.breadcrumbs,
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def put(self, request: Request):
        """Update an existing project."""
        template_processor: Jinja2Templates = request.state.templates
        user = get_user(request.session.get("user", {}))
        session_maker = request.state.session_maker
        project_id = get_id_from_request_path(request, "project_id", schemas.ProjectId)
        async with session_maker() as session:
            if (
                project := await operations.get_project(
                    project_id, user, session, request.state.settings
                )
            ) is None:
                raise HTTPException(404, f"Project {project_id!r} not found.")
        form_instance = await forms.ProjectUpdateForm.get_validated_form_instance(
            request, disregard_id=project_id
        )
        logger.debug(f"{form_instance.has_validation_errors()=}")

        if form_instance.has_validation_errors():
            logger.debug("form did not validate")
            logger.debug(f"{form_instance.errors=}")

            async def event_streamer():
                template = template_processor.get_template("projects/update-form.html")
                rendered = template.render(
                    request=request,
                    project=schemas.ProjectReadDetail.from_db_instance(project),
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(event_streamer(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_update = schemas.ProjectUpdate(
            owner=user.id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            root_path=form_instance.root_path.data,
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
        )

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            """Handle successful processing of the project update background task.

            After receiving the final message with a success status, update the
            UI to reflect the changes.
            """
            project_details = await _get_project_details(request)
            rendered_message = message_template.render(
                status=final_message.status.value,
                message=f"{final_message.message}",
            )
            yield ServerSentEventGenerator.patch_elements(
                rendered_message,
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            template = template_processor.get_template("projects/detail-component.html")
            # need to update:
            # - project details section (name, description, links, ...)
            # - breadcrumbs (project name may have changed)
            # - page title (project name may have changed)
            # - clear the feedback section
            breadcrumbs_template = template_processor.get_template("breadcrumbs.html")
            yield ServerSentEventGenerator.patch_elements(
                breadcrumbs_template.render(
                    request=request, breadcrumbs=project_details.breadcrumbs
                ),
                selector=schemas.selector_info.breadcrumbs_selector,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                template.render(
                    request=request,
                    project=project_details.item,
                    pagination=project_details.pagination,
                    survey_missions=project_details.children,
                    permissions=project_details.permissions,
                ),
                selector=schemas.selector_info.main_content_selector,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                project_details.item.name.en,
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
                """<li>Updating project as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.update_project.send(
                raw_request_id=str(request_id),
                raw_project_id=str(project_id),
                raw_to_update=to_update.model_dump_json(),
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

    @csrf_protect
    @fancy_requires_auth
    async def delete(self, request: Request):
        """Delete a project."""
        user = get_user(request.session.get("user", {}))
        session_maker = request.state.session_maker
        project_id = get_id_from_request_path(request, "project_id", schemas.ProjectId)
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

        request_id = schemas.RequestId(uuid.uuid4())

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    data_test_id="processing-success-message",
                    status=final_message.status,
                    message=f"{final_message.message} - you will be redirected shortly.",
                ),
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            await asyncio.sleep(1)
            yield ServerSentEventGenerator.redirect(
                str(request.url_for("projects:list")),
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

        async def stream_events():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Deleting project as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )
            enqueued_message: Message = tasks.delete_project.send(
                raw_request_id=str(request_id),
                raw_project_id=str(project_id),
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
    async def post(self, request: Request):
        """Create a new survey mission belonging to the project."""
        user = get_user(request.session.get("user", {}))
        project_id = get_id_from_request_path(request, "project_id", schemas.ProjectId)
        session_maker = request.state.session_maker
        template_processor: Jinja2Templates = request.state.templates
        creation_form = await forms.SurveyMissionCreateForm.from_formdata(request)
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
        await creation_form.validate_on_submit()
        creation_form.validate_with_schema()
        async with session_maker() as session:
            await creation_form.check_if_english_name_is_unique_for_project(
                session, project_id
            )

        if creation_form.has_validation_errors():

            async def stream_validation_failed_events():
                logger.debug("form did not validate")
                template = template_processor.get_template(
                    "survey-missions/create-form.html"
                )
                rendered = template.render(
                    request=request,
                    form=creation_form,
                    project=project,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(stream_validation_failed_events(), 422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_create = schemas.SurveyMissionCreate(
            id=schemas.SurveyMissionId(uuid.uuid4()),
            project_id=project.id,
            owner=user.id,
            name=schemas.LocalizableDraftName(
                en=creation_form.name.en.data,
                pt=creation_form.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=creation_form.description.en.data,
                pt=creation_form.description.pt.data,
            ),
            relative_path=creation_form.relative_path.data,
            bbox_4326=(
                f"POLYGON(("
                f"{creation_form.bounding_box.min_lon.data} {creation_form.bounding_box.min_lat.data}, "
                f"{creation_form.bounding_box.max_lon.data} {creation_form.bounding_box.min_lat.data}, "
                f"{creation_form.bounding_box.max_lon.data} {creation_form.bounding_box.max_lat.data}, "
                f"{creation_form.bounding_box.min_lon.data} {creation_form.bounding_box.max_lat.data}, "
                f"{creation_form.bounding_box.min_lon.data} {creation_form.bounding_box.min_lat.data}"
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
                for lf in creation_form.links.entries
            ],
        )
        logger.info(f"{to_create=}")

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    data_test_id="processing-success-message",
                    status=final_message.status,
                    message=f"{final_message.message} - you will be redirected shortly.",
                ),
                selector=schemas.selector_info.main_content_selector,
                mode=ElementPatchMode.APPEND,
            )
            await asyncio.sleep(1)
            yield ServerSentEventGenerator.redirect(
                str(
                    request.url_for(
                        "survey_missions:detail",
                        survey_mission_id=to_create.id,
                    )
                ),
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

        async def stream_events():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Creating survey mission as a background task...</li>""",
                selector=schemas.selector_info.feedback_selector,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.create_survey_mission.send(
                raw_request_id=str(request_id),
                raw_to_create=to_create.model_dump_json(),
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

        return DatastarResponse(stream_events(), status_code=202)


@csrf_protect
async def add_create_project_form_link(request: Request):
    """Add a form link to a create_project form."""
    creation_form = await forms.ProjectCreateForm.from_formdata(request)
    creation_form.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/create-form.html")
    rendered = template.render(
        form=creation_form,
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
async def remove_create_project_form_link(request: Request):
    """Remove a form link from a create_project form."""
    creation_form = await forms.ProjectCreateForm.from_formdata(request)
    link_index = int(request.query_params["link_index"])
    creation_form.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/create-form.html")
    rendered = template.render(
        form=creation_form,
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
async def add_update_project_form_link(request: Request):
    """Add a form link to an update_project form."""
    details = await _get_project_details(request)
    form_ = await forms.ProjectUpdateForm.from_formdata(request)
    form_.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/update-form.html")
    rendered = template.render(
        form=form_,
        project=details.item,
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
async def remove_update_project_form_link(request: Request):
    """Remove a form link from an update_project form."""
    details = await _get_project_details(request)
    form_ = await forms.ProjectUpdateForm.from_formdata(request)
    link_index = int(request.query_params["link_index"])
    form_.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/update-form.html")
    rendered = template.render(
        form=form_,
        project=details.item,
        request=request,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=schemas.selector_info.main_content_selector,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


routes = [
    Route("/", ProjectCollectionEndpoint, name="list"),
    Route("/search", get_list_component, name="get_list_component"),
    Route(
        "/new/add-form-link",
        add_create_project_form_link,
        methods=["POST"],
        name="add_form_link",
    ),
    Route(
        "/new/remove-form-link",
        remove_create_project_form_link,
        methods=["POST"],
        name="remove_form_link",
    ),
    Route(
        "/new",
        get_project_creation_form,
        methods=["GET"],
        name="get_creation_form",
    ),
    Route(
        "/{project_id}/update",
        get_project_update_form,
        methods=["GET"],
        name="get_update_form",
    ),
    Route(
        "/{project_id}/add-update-form-link",
        add_update_project_form_link,
        methods=["POST"],
        name="add_update_form_link",
    ),
    Route(
        "/{project_id}/remove-update-form-link",
        remove_update_project_form_link,
        methods=["POST"],
        name="remove_update_form_link",
    ),
    Route(
        "/{project_id}/details",
        get_project_details_component,
        methods=["GET"],
        name="get_details_component",
    ),
    Route(
        "/{project_id}",
        ProjectDetailEndpoint,
        name="detail",
    ),
]
