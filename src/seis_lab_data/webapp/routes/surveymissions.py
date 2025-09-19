import dataclasses
import json
import logging
import uuid

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
from dramatiq import Message
from redis.asyncio import Redis
from starlette_babel import gettext_lazy as _
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from starlette_wtf import csrf_protect

from seis_lab_data import (
    errors,
    operations,
    schemas,
)
from ... import permissions
from ...processing import tasks
from .. import forms
from .auth import (
    fancy_requires_auth,
    get_user,
)
from .common import produce_event_stream_for_topic

logger = logging.getLogger(__name__)


@csrf_protect
@fancy_requires_auth
async def get_survey_mission_creation_form(request: Request):
    user = get_user(request.session.get("user", {}))
    project_id = schemas.ProjectId(uuid.UUID(request.path_params["project_id"]))
    session_maker = request.state.session_maker
    template_processor: Jinja2Templates = request.state.templates
    create_survey_mission_form = await forms.SurveyMissionCreateForm.from_formdata(
        request
    )

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

    return template_processor.TemplateResponse(
        request,
        "survey-missions/create.html",
        context={
            "form": create_survey_mission_form,
            "project": schemas.ProjectReadDetail.from_db_instance(project),
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(
                    name=_("Projects"),
                    url=request.url_for("projects:list"),
                ),
                schemas.BreadcrumbItem(
                    name=str(project.id),
                    url=request.url_for("projects:detail", project_id=project_id),
                ),
                schemas.BreadcrumbItem(
                    name=_("New survey mission"),
                ),
            ],
        },
    )


class SurveyMissionCollectionEndpoint(HTTPEndpoint):
    """Manage collection of survey missions."""

    async def get(self, request: Request):
        """List survey missions."""
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            items, num_total = await operations.list_survey_missions(
                session,
                initiator=user.id if user else None,
                limit=request.query_params.get("limit", 20),
                offset=request.query_params.get("offset", 0),
                include_total=True,
            )
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "survey-missions/list.html",
            context={
                "items": [
                    schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
                ],
                "num_total": num_total,
                "breadcrumbs": [
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Survey Missions")),
                ],
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        """Create a new record in the survey mission's collection."""
        ...


class SurveyMissionDetailEndpoint(HTTPEndpoint):
    """Survey mission detail endpoint."""

    async def get(self, request: Request):
        survey_mission_id = schemas.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
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
            (
                survey_related_records,
                total,
            ) = await operations.list_survey_related_records(
                session,
                user,
                survey_mission_filter=survey_mission_id,
                include_total=True,
            )
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "survey-missions/detail.html",
            context={
                "item": schemas.SurveyMissionReadDetail.from_db_instance(
                    survey_mission
                ),
                "survey_related_records": {
                    "survey_related_records": [
                        schemas.SurveyRelatedRecordReadListItem(**srr.model_dump())
                        for srr in survey_related_records
                    ],
                    "total": total,
                },
                "user_can_delete": await permissions.can_delete_survey_mission(
                    user, survey_mission_id, settings=request.state.settings
                ),
                "user_can_create_survey_related_record": await permissions.can_create_survey_related_record(
                    user,
                    survey_mission_id=survey_mission_id,
                    settings=request.state.settings,
                ),
                "breadcrumbs": [
                    schemas.BreadcrumbItem(
                        name=_("Home"), url=str(request.url_for("home"))
                    ),
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
            },
        )

    async def delete(self, request: Request):
        survey_mission_id = schemas.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
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

        async def stream_events():
            request_id = schemas.RequestId(uuid.uuid4())
            yield ServerSentEventGenerator.patch_elements(
                """<li>Deleting survey mission as a background task...</li>""",
                selector="#feedback > ul",
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
                topic_name=f"progress:{request_id}",
                success_redirect_url=str(
                    request.url_for(
                        "projects:detail", project_id=survey_mission.project.id
                    )
                ),
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())
