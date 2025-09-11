import asyncio
import dataclasses
import json
import logging
import uuid

import pydantic
from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
from dramatiq import Message
from redis.asyncio import Redis
from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette_wtf import csrf_protect

from .. import (
    constants,
    errors,
    operations,
    permissions,
    schemas,
)
from ..processing import tasks
from . import forms
from .auth import (
    get_user,
    requires_auth,
)

logger = logging.getLogger(__name__)


async def list_projects(request: Request):
    """List projects."""
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        items, num_total = await operations.list_projects(
            session,
            initiator=user.id if user else None,
            limit=request.query_params.get("limit", 20),
            offset=request.query_params.get("offset", 0),
            include_total=True,
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "projects/list.html",
        context={
            "items": [schemas.ProjectReadListItem.from_db_instance(i) for i in items],
            "num_total": num_total,
            "breadcrumbs": [
                schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                schemas.BreadcrumbItem(name=_("Projects")),
            ],
            "user_can_create": await permissions.can_create_project(
                user, request.state.settings
            ),
        },
    )


async def get_project(request: Request):
    """Get project."""
    user = get_user(request.session.get("user", {}))
    session_maker = request.state.session_maker
    slug = request.path_params["project_slug"]
    if request.method == "GET":
        async with session_maker() as session:
            try:
                project = await operations.get_project_by_slug(
                    slug,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if project is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Project {slug!r} not found.")
                )
            project_id = schemas.ProjectId(project.id)
            survey_missions, total = await operations.list_survey_missions(
                session, user, project_filter=project_id, include_total=True
            )
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "projects/detail.html",
            context={
                "item": schemas.ProjectReadDetail(**project.model_dump()),
                "survey_missions": {
                    "survey_missions": [
                        schemas.SurveyMissionReadListItem(**sm.model_dump())
                        for sm in survey_missions
                    ],
                    "total": total,
                },
                "user_can_delete": await permissions.can_delete_project(
                    user, project_id, settings=request.state.settings
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
    elif request.method == "DELETE":
        async with session_maker() as session:
            try:
                project = await operations.get_project_by_slug(
                    slug,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if project is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Project {slug!r} not found.")
                )
            project_id = schemas.ProjectId(project.id)

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
            event_stream_generator = _produce_event_stream_for_topic(
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
@requires_auth
async def create_project(request: Request, user: schemas.User):
    template_processor: Jinja2Templates = request.state.templates
    create_project_form = await forms.ProjectCreateForm.from_formdata(request)
    if request.method == "GET":
        return template_processor.TemplateResponse(
            request,
            "projects/create.html",
            context={
                "form": create_project_form,
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
    elif request.method == "POST":

        async def stream_events():
            if await create_project_form.validate_on_submit():
                request_id = schemas.RequestId(uuid.uuid4())
                try:
                    to_create = schemas.ProjectCreate(
                        id=schemas.ProjectId(uuid.uuid4()),
                        owner=user.id,
                        name={
                            "en": create_project_form.name_en.data,
                            "pt": create_project_form.name_pt.data,
                        },
                        description={
                            "en": create_project_form.description_en.data,
                            "pt": create_project_form.description_pt.data,
                        },
                        root_path=create_project_form.root_path.data,
                    )
                except pydantic.ValidationError as exc:
                    for error in exc.errors():
                        logger.debug(f"{error=}")
                        message = error["msg"]
                        if error["loc"][0] == "name":
                            lang = error["ctx"]["language"]
                            field_name = f"name_{lang}"
                            if error["type"] == "missing_english_locale_value":
                                message = _("English name is required")
                        else:
                            field_name = error["loc"][0]
                        getattr(create_project_form, field_name).errors.append(message)

                    logger.debug("pydantic schema did not validate")
                    template = template_processor.get_template(
                        "projects/create-form.html"
                    )
                    rendered = template.render(
                        form=create_project_form,
                        request=request,
                    )
                    yield ServerSentEventGenerator.patch_elements(
                        rendered,
                        selector="#project-create-form-container",
                        mode=ElementPatchMode.INNER,
                    )
                else:
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
                    event_stream_generator = _produce_event_stream_for_topic(
                        redis_client,
                        request,
                        topic_name=f"progress:{request_id}",
                        success_redirect_url=str(
                            request.url_for(
                                "projects:detail", project_slug=to_create.slug
                            )
                        ),
                        timeout_seconds=30,
                    )
                    async for sse_event in event_stream_generator:
                        yield sse_event

            else:
                logger.debug("form did not validate")
                form_response = template_processor.TemplateResponse(
                    request,
                    "projects/create-form.html",
                    context={
                        "form": create_project_form,
                    },
                )
                yield ServerSentEventGenerator.patch_elements(
                    form_response,
                    selector="#project-create-form-container",
                    mode=ElementPatchMode.INNER,
                )

        return DatastarResponse(stream_events())


async def _produce_event_stream_for_topic(
    redis_client: Redis,
    request: Request,
    topic_name: str,
    success_redirect_url: str,
    timeout_seconds: int = 30,
):
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(topic_name)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"client disconnected from topic {topic_name!r}")
                    break
                try:
                    if message := await pubsub.get_message(
                        ignore_subscribe_messages=False, timeout=timeout_seconds
                    ):
                        if message["type"] == "subscribe":
                            logger.debug(f"Subscribed to topic {topic_name!r}")
                        elif message["type"] == "message":
                            processing_message = schemas.ProcessingMessage(
                                **json.loads(message["data"])
                            )
                            logger.debug(f"Received message: {processing_message!r}")
                            yield ServerSentEventGenerator.patch_elements(
                                f"<li>{processing_message.status.get_translated_value()} "
                                f"- {processing_message.message}</li>",
                                selector="#feedback > ul",
                                mode=ElementPatchMode.APPEND,
                            )
                            if processing_message.status in (
                                constants.ProcessingStatus.SUCCESS,
                                constants.ProcessingStatus.FAILED,
                            ):
                                if (
                                    processing_message.status
                                    == constants.ProcessingStatus.SUCCESS
                                ):
                                    yield ServerSentEventGenerator.patch_elements(
                                        "<li>Processing completed successfully - you will be redirected shortly</li>",
                                        selector="#feedback > ul",
                                        mode=ElementPatchMode.APPEND,
                                    )
                                    await asyncio.sleep(1)
                                    yield ServerSentEventGenerator.redirect(
                                        success_redirect_url
                                    )
                                break
                    else:
                        logging.info(
                            f"pubsub listener for topic {topic_name!r} timed out after {timeout_seconds} seconds"
                        )
                        break
                except asyncio.CancelledError:
                    logger.info(
                        f"pubsub listener for topic {topic_name!r} was cancelled"
                    )
                    raise
        finally:
            await pubsub.unsubscribe(topic_name)


@csrf_protect
async def add_create_project_form_link(request: Request):
    """Add a form link to a create_project form."""
    create_project_form = await forms.ProjectCreateForm.from_formdata(request)
    create_project_form.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/create-form.html")
    rendered = template.render(
        form=create_project_form,
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
    create_project_form = await forms.ProjectCreateForm.from_formdata(request)
    link_index = int(request.path_params["link_index"])
    create_project_form.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("projects/create-form.html")
    rendered = template.render(
        form=create_project_form,
        request=request,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#project-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@requires_auth
async def delete_project(request: Request, user: schemas.User):
    """Delete an existing project."""

    async def stream_events():
        request_id = schemas.RequestId(uuid.uuid4())
        project_id = (schemas.ProjectId(request.path_params["project_slug"]),)
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
        event_stream_generator = _produce_event_stream_for_topic(
            redis_client,
            request,
            topic_name=f"progress:{request_id}",
            success_redirect_url=str(request.url_for("projects:list")),
            timeout_seconds=30,
        )
        async for sse_event in event_stream_generator:
            yield sse_event

    return DatastarResponse(stream_events())


routes = [
    Route("/", list_projects, methods=["GET"], name="list"),
    Route(
        "/new/add-form-link",
        add_create_project_form_link,
        methods=["POST"],
        name="add_form_link",
    ),
    Route(
        "/new/remove-form-link/{link_index}",
        remove_create_project_form_link,
        methods=["POST"],
        name="remove_form_link",
    ),
    Route("/new", create_project, methods=["GET", "POST"], name="create"),
    Route("/{project_slug}", get_project, methods=["GET", "DELETE"], name="detail"),
    Route("/{project_slug}/delete", delete_project, methods=["POST"], name="delete"),
]
