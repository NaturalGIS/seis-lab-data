import json
import logging
import uuid

from aioredis import Redis
from datastar_py import ServerSentEventGenerator
from datastar_py.starlette import DatastarResponse
from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route
from starlette_wtf import csrf_protect

from .. import (
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
            "items": [
                schemas.ProjectReadListItem(
                    **i.model_dump(),
                )
                for i in items
            ],
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
    slug = request.path_params["project_slug"]
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
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
@requires_auth
async def create_project(request: Request, user: schemas.User):
    template_processor = request.state.templates
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
            yield ServerSentEventGenerator.patch_elements(
                """<div id="feedback">This is me from the backend :heart:</div>""",
                selector="#feedback",
            )

            if await create_project_form.validate_on_submit():
                request_id = schemas.RequestId(uuid.uuid4())
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
                logger.debug(f"{request_id=}")
                logger.debug(f"{to_create=}")
                enqueued_message = tasks.create_project.send(
                    raw_request_id=str(request_id),
                    raw_to_create=to_create.model_dump_json(),
                )
                logger.debug(f"{enqueued_message=}")

                redis_client: Redis = request.state.redis_client
                pubsub = redis_client.pubsub()
                topic_name = f"progress:{request_id}"
                await pubsub.subscribe(topic_name)
                try:
                    while True:
                        if message := await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=30
                        ):
                            status_update = json.loads(message["data"])
                            status = status_update.get("status")
                            yield ServerSentEventGenerator.patch_elements(
                                f"Status: {status_update}",
                                selector="#feedback",
                            )
                            if status in ("finished", "failed"):
                                break
                        if await request.is_disconnected():
                            break
                finally:
                    await pubsub.unsubscribe(topic_name)
                    await pubsub.close()
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
                )

        return DatastarResponse(stream_events())


routes = [
    Route("/", list_projects, methods=["GET"], name="list"),
    Route("/new", create_project, methods=["GET", "POST"], name="create"),
    Route("/{project_slug}", get_project, methods=["GET"], name="detail"),
]
