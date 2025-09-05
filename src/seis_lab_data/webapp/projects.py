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
from . import forms
from .auth import get_user


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
            "user_can_create": permissions.can_create_project(
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
async def create_project(request: Request):
    create_project_form = await forms.ProjectCreateForm.from_formdata(request)
    if await create_project_form.validate_on_submit():
        ...
    template_processor = request.state.templates
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


routes = [
    Route("/", list_projects, methods=["GET"], name="list"),
    Route("/new", create_project, methods=["GET", "POST"], name="create"),
    Route("/{project_slug}", get_project, methods=["GET"], name="detail"),
]
