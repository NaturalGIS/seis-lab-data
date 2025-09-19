import uuid

from starlette_babel import gettext_lazy as _
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from starlette_wtf import csrf_protect

from ... import (
    errors,
    operations,
    schemas,
)
from .. import forms
from .auth import (
    get_user,
    fancy_requires_auth,
)


@csrf_protect
@fancy_requires_auth
async def get_survey_related_record_creation_form(request: Request):
    """Get survey-related record creation form."""
    user = get_user(request.session.get("user", {}))
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    session_maker = request.state.session_maker
    template_processor: Jinja2Templates = request.state.templates
    creation_form = await forms.SurveyRelatedRecordCreateForm.from_formdata(request)

    async with session_maker() as session:
        try:
            survey_mission = await operations.get_survey_mission(
                survey_mission_id, user, session, request.state.settings
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_mission is None:
            raise HTTPException(
                status_code=404,
                detail=_(f"Survey mission {survey_mission_id!r} not found."),
            )

    return template_processor.TemplateResponse(
        request,
        "survey-related-records/create.html",
        context={
            "form": creation_form,
            "survey_mission": schemas.SurveyMissionReadDetail.from_db_instance(
                survey_mission
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
                    name=str(survey_mission.project.name["en"]),
                    url=request.url_for(
                        "projects:detail", project_id=survey_mission.project.id
                    ),
                ),
                schemas.BreadcrumbItem(
                    name=str(survey_mission.name["en"]),
                    url=request.url_for(
                        "survey_missions:detail",
                        survey_mission_id=survey_mission_id,
                    ),
                ),
                schemas.BreadcrumbItem(
                    name=_("New survey-related record"),
                ),
            ],
        },
    )


class SurveyRelatedRecordCollectionEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
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


class SurveyRelatedRecordDetailEndpoint(HTTPEndpoint):
    async def get_survey_related_record(self, request: Request):
        """Get survey-related record."""
        survey_related_record_id = schemas.SurveyRelatedRecordId(
            uuid.UUID(request.path_params["survey_related_record_id"])
        )
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            try:
                survey_record = await operations.get_survey_related_record(
                    survey_related_record_id,
                    user or None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_record is None:
            raise HTTPException(
                status_code=404,
                detail=_(
                    f"Survey-related record {survey_related_record_id!r} not found."
                ),
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
