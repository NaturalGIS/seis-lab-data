import logging
import uuid

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
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
from ...db import (
    models,
    queries,
)
from .. import forms
from .auth import (
    get_user,
    fancy_requires_auth,
)

logger = logging.getLogger(__name__)


@csrf_protect
async def add_create_survey_related_record_form_asset_link(request: Request):
    """Add an asset link form to a create_survey_related_record form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    asset_index = int(request.path_params["asset_index"])
    creation_form, survey_mission = await _get_creation_form(request)
    creation_form.assets[asset_index].asset_links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_related_record_form_asset_link(request: Request):
    """Remove an asset link form to a create_survey_related_record form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    asset_index = int(request.path_params["asset_index"])
    link_index = int(request.query_params.get("link_index", 0))
    creation_form, survey_mission = await _get_creation_form(request)
    creation_form.assets[asset_index].asset_links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_create_survey_related_record_form_asset(request: Request):
    """Add an asset form to a create_survey_related_record form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    creation_form, survey_mission = await _get_creation_form(request)
    creation_form.assets.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_related_record_form_asset(request: Request):
    """Remove an asset from a create_survey_related_record form."""

    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    creation_form, survey_mission = await _get_creation_form(request)
    asset_index = int(request.query_params.get("asset_index", 0))
    creation_form.assets.entries.pop(asset_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def add_create_survey_related_record_form_link(request: Request):
    """Add a form link to a create_survey_related_record form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    creation_form, survey_mission = await _get_creation_form(request)
    creation_form.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_related_record_form_link(request: Request):
    """Remove a form link from a create_survey_related_record form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    creation_form, survey_mission = await _get_creation_form(request)
    link_index = int(request.query_params.get("link_index", 0))
    creation_form.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=creation_form,
        request=request,
        survey_mission_id=survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


async def _get_creation_form(
    request: Request,
) -> tuple[forms.SurveyRelatedRecordCreateForm, models.SurveyMission]:
    user = get_user(request.session.get("user", {}))
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    session_maker = request.state.session_maker
    creation_form = await forms.SurveyRelatedRecordCreateForm.from_formdata(request)
    current_language = request.state.language

    async with session_maker() as session:
        try:
            creation_form.dataset_category_id.choices = [
                (dc.id, dc.name.get(current_language, dc.name["en"]))
                for dc in await queries.collect_all_dataset_categories(
                    session,
                    order_by_clause=models.DatasetCategory.name[
                        current_language
                    ].astext,
                )
            ]
            creation_form.domain_type_id.choices = [
                (dt.id, dt.name.get(current_language, dt.name["en"]))
                for dt in await queries.collect_all_domain_types(
                    session,
                    order_by_clause=models.DomainType.name[current_language].astext,
                )
            ]
            creation_form.workflow_stage_id.choices = [
                (ws.id, ws.name.get(current_language, ws.name["en"]))
                for ws in await queries.collect_all_workflow_stages(
                    session,
                    order_by_clause=models.WorkflowStage.name[current_language].astext,
                )
            ]

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
    return creation_form, survey_mission


@csrf_protect
@fancy_requires_auth
async def get_survey_related_record_creation_form(request: Request):
    """Get survey-related record creation form."""
    survey_mission_id = schemas.SurveyMissionId(
        uuid.UUID(request.path_params["survey_mission_id"])
    )
    creation_form, survey_mission = await _get_creation_form(request)
    template_processor: Jinja2Templates = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-related-records/create.html",
        context={
            "form": creation_form,
            "survey_mission_id": survey_mission_id,
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
