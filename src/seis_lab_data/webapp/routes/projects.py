import dataclasses
import json
import logging
import uuid

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
from dramatiq import Message
from redis.asyncio import Redis
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
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
from .auth import (
    get_user,
    fancy_requires_auth,
)
from .common import (
    get_pagination_info,
    produce_event_stream_for_topic,
)

logger = logging.getLogger(__name__)


@csrf_protect
@fancy_requires_auth
async def get_project_creation_form(request: Request):
    """Return a form suitable for creating a new project."""
    template_processor: Jinja2Templates = request.state.templates
    creation_form = await forms.ProjectCreateForm.from_formdata(request)
    return template_processor.TemplateResponse(
        request,
        "projects/create.html",
        context={
            "form": creation_form,
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(
                    name=_("Projects"),
                    url=request.url_for("projects:list"),
                ),
                schemas.BreadcrumbItem(
                    name=_("New Project"),
                ),
            ],
        },
    )


class ProjectCollectionEndpoint(HTTPEndpoint):
    """Manage the collection of projects."""

    async def get(self, request: Request):
        """List projects."""
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        settings: config.SeisLabDataSettings = request.state.settings
        try:
            current_page = int(request.query_params.get("page", 1))
            if current_page < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid page number")
        async with session_maker() as session:
            items, num_total = await operations.list_projects(
                session,
                initiator=user or None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
            )
            num_unfiltered_total = (
                await operations.list_projects(
                    session, initiator=user or None, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page, settings.pagination_page_size, num_total, num_unfiltered_total
        )
        return template_processor.TemplateResponse(
            request,
            "projects/list.html",
            context={
                "items": [
                    schemas.ProjectReadListItem.from_db_instance(i) for i in items
                ],
                "pagination": pagination_info,
                "breadcrumbs": [
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Projects")),
                ],
                "user_can_create": await permissions.can_create_project(
                    user, request.state.settings
                ),
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        """Create a new project."""
        template_processor: Jinja2Templates = request.state.templates
        user = get_user(request.session.get("user", {}))
        creation_form = await forms.ProjectCreateForm.from_formdata(request)
        # first validate the form with WTForms' validation logic
        # then validate the form data with our custom pydantic model
        await creation_form.validate_on_submit()
        creation_form.validate_with_schema()
        session_maker = request.state.session_maker
        async with session_maker() as session:
            await creation_form.check_if_english_name_is_unique(session)
        form_is_valid = creation_form.has_validation_errors()

        async def stream_events():
            if form_is_valid:
                request_id = schemas.RequestId(uuid.uuid4())
                to_create = schemas.ProjectCreate(
                    id=schemas.ProjectId(uuid.uuid4()),
                    owner=user.id,
                    name=schemas.LocalizableDraftName(
                        en=creation_form.name.en.data,
                        pt=creation_form.name.pt.data,
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en=creation_form.description.en.data,
                        pt=creation_form.description.pt.data,
                    ),
                    root_path=creation_form.root_path.data,
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

                yield ServerSentEventGenerator.patch_elements(
                    """<li>Creating project as a background task...</li>""",
                    selector="#feedback > ul",
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
                    success_redirect_url=str(
                        request.url_for("projects:detail", project_id=to_create.id)
                    ),
                    timeout_seconds=30,
                )
                async for sse_event in event_stream_generator:
                    yield sse_event

            else:
                logger.debug("form did not validate")
                template = template_processor.get_template("projects/create-form.html")
                rendered = template.render(
                    request=request,
                    form=creation_form,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector="#project-create-form-container",
                    mode=ElementPatchMode.INNER,
                )

        return DatastarResponse(
            stream_events(), status_code=202 if form_is_valid else 422
        )


class ProjectDetailEndpoint(HTTPEndpoint):
    """Manage a single project and its collection of survey missions."""

    async def get(self, request: Request):
        """
        Get project details and provide a paginated list of its survey missions.
        """
        try:
            current_page = int(request.query_params.get("page", 1))
            if current_page < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid page number")
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
            survey_missions, total = await operations.list_survey_missions(
                session, user, project_filter=project_id, include_total=True
            )
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page, request.state.settings.pagination_page_size, total, total
        )
        return template_processor.TemplateResponse(
            request,
            "projects/detail.html",
            context={
                "item": schemas.ProjectReadDetail(**project.model_dump()),
                "pagination": pagination_info,
                "survey_missions": {
                    "survey_missions": [
                        schemas.SurveyMissionReadListItem.from_db_instance(sm)
                        for sm in survey_missions
                    ],
                    "total": total,
                },
                "user_can_delete": await permissions.can_delete_project(
                    user, project_id, settings=request.state.settings
                ),
                "user_can_create_survey_mission": await permissions.can_create_survey_mission(
                    user, project_id=project_id, settings=request.state.settings
                ),
                "breadcrumbs": [
                    schemas.BreadcrumbItem(
                        name=_("Home"), url=str(request.url_for("home"))
                    ),
                    schemas.BreadcrumbItem(
                        name=_("Projects"),
                        url=request.url_for("projects:list"),
                    ),
                    schemas.BreadcrumbItem(
                        name=project.name["en"],
                    ),
                ],
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        """Create a new survey mission belonging to the project."""
        user = get_user(request.session.get("user", {}))
        project_id = schemas.ProjectId(uuid.UUID(request.path_params["project_id"]))
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
        form_is_valid = creation_form.has_validation_errors()

        async def stream_events():
            # first validate the form with WTForms' validation logic
            # then validate the form data with our custom pydantic model
            if form_is_valid:
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

                yield ServerSentEventGenerator.patch_elements(
                    """<li>Creating survey mission as a background task...</li>""",
                    selector="#feedback > ul",
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
                    success_redirect_url=str(
                        request.url_for(
                            "survey_missions:detail",
                            survey_mission_id=to_create.id,
                        )
                    ),
                    timeout_seconds=30,
                )
                async for sse_event in event_stream_generator:
                    yield sse_event

            else:
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
                    selector="#survey-mission-create-form-container",
                    mode=ElementPatchMode.INNER,
                )

        return DatastarResponse(
            stream_events(), status_code=202 if form_is_valid else 422
        )

    @fancy_requires_auth
    async def delete(self, request: Request):
        """Delete a project."""
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

        async def stream_events():
            request_id = schemas.RequestId(uuid.uuid4())
            yield ServerSentEventGenerator.patch_elements(
                """<li>Deleting project as a background task...</li>""",
                selector="#feedback > ul",
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
                success_redirect_url=str(request.url_for("projects:list")),
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())


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
            selector="#project-create-form-container",
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
            selector="#project-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())
