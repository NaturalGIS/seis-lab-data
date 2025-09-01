from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route

from .. import (
    operations,
    schemas,
)
from ..auth import get_user


async def list_projects(request: Request):
    """List projects."""
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        items, num_total = await operations.list_projects(
            session,
            initiator=user,
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
        },
    )


async def get_project(request: Request):
    """Get project."""
    slug = request.path_params["project_slug"]
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        project = await operations.get_project_by_slug(
            slug,
            user,
            session,
            request.state.settings,
        )
    if project is None:
        raise HTTPException(status_code=404, detail=_(f"Project {slug!r} not found."))
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "projects/detail.html",
        context={
            "item": schemas.ProjectReadDetail(**project.model_dump()),
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


routes = [
    Route("/", list_projects, methods=["GET"], name="list"),
    Route("/{project_slug}", get_project, methods=["GET"], name="detail"),
]
