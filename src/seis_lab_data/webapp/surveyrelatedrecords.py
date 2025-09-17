from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route

from .. import (
    errors,
    operations,
    schemas,
)
from .auth import get_user


async def list_survey_related_records(request: Request):
    """List survey-related records."""
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        items, num_total = await operations.list_survey_related_records(
            session,
            initiator=user.id if user else None,
            limit=request.query_params.get("limit", 20),
            offset=request.query_params.get("offset", 0),
            include_total=True,
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-related-records/list.html",
        context={
            "items": [
                schemas.SurveyRelatedRecordReadListItem(
                    **i.model_dump(),
                )
                for i in items
            ],
            "num_total": num_total,
            "breadcrumbs": [
                schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                schemas.BreadcrumbItem(name=_("Survey-related records")),
            ],
        },
    )


async def get_survey_related_record(request: Request):
    """Get survey-related record."""
    slug = request.path_params["survey_related_record_slug"]
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        try:
            survey_record = await operations.get_survey_related_record_by_slug(
                slug,
                user.id if user else None,
                session,
                request.state.settings,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    if survey_record is None:
        raise HTTPException(
            status_code=404, detail=_(f"Survey-related record {slug!r} not found.")
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-related-records/detail.html",
        context={
            "item": schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                survey_record
            ),
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(
                    name=_("Survey-related records"),
                    url=request.url_for("survey_related_records:list"),
                ),
                schemas.BreadcrumbItem(
                    name=survey_record.name["en"],
                ),
            ],
        },
    )


routes = [
    Route("/", list_survey_related_records, methods=["GET"], name="list"),
    Route(
        "/{survey_related_record_slug}",
        get_survey_related_record,
        methods=["GET"],
        name="detail",
    ),
]
