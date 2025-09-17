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


async def list_survey_missions(request: Request):
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


class SurveyMissionDetailEndpoint(HTTPEndpoint):
    """Survey mission detail endpoint."""

    async def get(self, request: Request):
        project_slug = request.path_params["project_slug"]
        slug = request.path_params["survey_mission_slug"]
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            try:
                survey_mission = await operations.get_survey_mission_by_slug(
                    slug,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if survey_mission is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Survey mission {slug!r} not found.")
                )
            if survey_mission.project.slug != project_slug:
                raise HTTPException(
                    status_code=404, detail=_(f"Invalid project slug {slug!r}.")
                )
            survey_mission_id = schemas.SurveyMissionId(survey_mission.id)
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
                        name=survey_mission.project.slug,
                        url=str(
                            request.url_for(
                                "projects:detail",
                                project_slug=survey_mission.project.slug,
                            )
                        ),
                    ),
                    schemas.BreadcrumbItem(
                        name=_("Survey Missions"),
                        url=request.url_for("survey_missions:list"),
                    ),
                    schemas.BreadcrumbItem(
                        name=survey_mission.slug,
                    ),
                ],
            },
        )

    async def delete(self, request: Request):
        project_slug = request.path_params["project_slug"]
        slug = request.path_params["survey_mission_slug"]
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            try:
                survey_mission = await operations.get_survey_mission_by_slug(
                    slug,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if survey_mission is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Survey mission {slug!r} not found.")
                )
            if survey_mission.project.slug != project_slug:
                raise HTTPException(
                    status_code=404, detail=_(f"Invalid project slug {slug!r}.")
                )
            survey_mission_id = schemas.SurveyMissionId(survey_mission.id)

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
                    request.url_for("projects:detail", project_slug=project_slug)
                ),
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())


class SurveyMissionCreationEndpoint(HTTPEndpoint):
    @csrf_protect
    @fancy_requires_auth
    async def get(self, request: Request):
        user = get_user(request.session.get("user", {}))
        project_slug = request.path_params["project_slug"]
        session_maker = request.state.session_maker
        template_processor: Jinja2Templates = request.state.templates
        create_survey_mission_form = await forms.SurveyMissionCreateForm.from_formdata(
            request
        )

        async with session_maker() as session:
            try:
                project = await operations.get_project_by_slug(
                    project_slug, user, session, request.state.settings
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if project is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Project {project_slug!r} not found.")
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
                        name=project.slug,
                        url=request.url_for(
                            "projects:detail", project_slug=project_slug
                        ),
                    ),
                    schemas.BreadcrumbItem(
                        name=_("New survey mission"),
                    ),
                ],
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        user = get_user(request.session.get("user", {}))
        project_slug = request.path_params["project_slug"]
        session_maker = request.state.session_maker
        template_processor: Jinja2Templates = request.state.templates
        create_survey_mission_form = await forms.SurveyMissionCreateForm.from_formdata(
            request
        )
        async with session_maker() as session:
            try:
                project = await operations.get_project_by_slug(
                    project_slug, user, session, request.state.settings
                )
            except errors.SeisLabDataError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if project is None:
                raise HTTPException(
                    status_code=404, detail=_(f"Project {project_slug!r} not found.")
                )

        async def stream_events():
            # first validate the form with WTForms' validation logic
            # then validate the form data with our custom pydantic model
            await create_survey_mission_form.validate_on_submit()
            forms.validate_form_with_model(
                create_survey_mission_form,
                schemas.SurveyMissionCreate,
            )
            # For some unknown reason, wtforms does not report validation errors for
            # the 'links' listfield together with the other validation errors. This may
            # have something to with the fact that we are setting the 'errors' property
            # of fields manually. Anyway, we need to emply the below workaround in order
            # to verify if the form contains any erors.
            all_form_validation_errors = {**create_survey_mission_form.errors}
            for link in create_survey_mission_form.links.entries:
                all_form_validation_errors.update(**link.errors)
            if not all_form_validation_errors:
                request_id = schemas.RequestId(uuid.uuid4())
                to_create = schemas.SurveyMissionCreate(
                    id=schemas.SurveyMissionId(uuid.uuid4()),
                    project_id=project.id,
                    owner=user.id,
                    name=schemas.LocalizableDraftName(
                        en=create_survey_mission_form.name.en.data,
                        pt=create_survey_mission_form.name.pt.data,
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en=create_survey_mission_form.description.en.data,
                        pt=create_survey_mission_form.description.pt.data,
                    ),
                    relative_path=create_survey_mission_form.relative_path.data,
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
                        for lf in create_survey_mission_form.links.entries
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
                            "projects:survey_mission",
                            project_slug=project.slug,
                            survey_mission_slug=to_create.slug,
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
                    form=create_survey_mission_form,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector="#survey-mission-create-form-container",
                    mode=ElementPatchMode.INNER,
                )

        return DatastarResponse(stream_events())
