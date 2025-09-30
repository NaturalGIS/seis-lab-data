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
    fancy_requires_auth,
    get_user,
)
from .common import (
    get_pagination_info,
    produce_event_stream_for_topic,
)
from .surveyrelatedrecords import generate_survey_related_record_creation_form

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
        settings: config.SeisLabDataSettings = request.state.settings
        try:
            current_page = int(request.query_params.get("page", 1))
            if current_page < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid page number")
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            items, num_total = await operations.list_survey_missions(
                session,
                initiator=user.id if user else None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
            )
            num_unfiltered_total = (
                await operations.list_survey_missions(
                    session, initiator=user or None, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page,
            settings.pagination_page_size,
            num_total,
            num_unfiltered_total,
            collection_url=str(request.url_for("survey_missions:list")),
        )
        return template_processor.TemplateResponse(
            request,
            "survey-missions/list.html",
            context={
                "items": [
                    schemas.SurveyMissionReadListItem.from_db_instance(i) for i in items
                ],
                "pagination": pagination_info,
                "breadcrumbs": [
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Survey Missions")),
                ],
            },
        )


class SurveyMissionDetailEndpoint(HTTPEndpoint):
    """Survey mission detail endpoint."""

    async def get(self, request: Request):
        survey_mission_id = schemas.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
        )
        try:
            current_page = int(request.query_params.get("page", 1))
            if current_page < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid page number")
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
        pagination_info = get_pagination_info(
            current_page,
            request.state.settings.pagination_page_size,
            total,
            total,
            collection_url=str(
                request.url_for(
                    "survey_missions:detail", survey_mission_id=survey_mission_id
                )
            ),
        )
        return template_processor.TemplateResponse(
            request,
            "survey-missions/detail.html",
            context={
                "item": schemas.SurveyMissionReadDetail.from_db_instance(
                    survey_mission
                ),
                "pagination": pagination_info,
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

    @csrf_protect
    @fancy_requires_auth
    async def post(self, request: Request):
        """Create a new record in the survey mission's collection."""
        user = get_user(request.session.get("user", {}))
        survey_mission_id = schemas.SurveyMissionId(
            uuid.UUID(request.path_params["survey_mission_id"])
        )
        (
            creation_form,
            survey_mission,
        ) = await generate_survey_related_record_creation_form(request)
        session_maker = request.state.session_maker
        template_processor: Jinja2Templates = request.state.templates
        try:
            await creation_form.validate_on_submit()
        except TypeError as err:
            logger.exception("Failed to create survey-related record creation form.")
            raise HTTPException(status_code=500) from err
        creation_form.validate_with_schema()
        async with session_maker() as session:
            await creation_form.check_if_english_name_is_unique_for_survey_mission(
                session, survey_mission_id
            )
        form_is_valid = creation_form.has_validation_errors()
        logger.debug(f"{form_is_valid=}")

        async def stream_events():
            if form_is_valid:
                request_id = schemas.RequestId(uuid.uuid4())
                to_create = schemas.SurveyRelatedRecordCreate(
                    id=schemas.SurveyRelatedRecordId(uuid.uuid4()),
                    survey_mission_id=survey_mission_id,
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
                    dataset_category_id=creation_form.dataset_category_id.data,
                    domain_type_id=creation_form.domain_type_id.data,
                    workflow_stage_id=creation_form.workflow_stage_id.data,
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
                    assets=[
                        schemas.RecordAssetCreate(
                            id=schemas.RecordAssetId(uuid.uuid4()),
                            name=schemas.LocalizableDraftName(
                                en=af.asset_name.en.data,
                                pt=af.asset_name.pt.data,
                            ),
                            description=schemas.LocalizableDraftDescription(
                                en=af.asset_description.en.data,
                                pt=af.asset_description.pt.data,
                            ),
                            relative_path=af.relative_path.data,
                            links=[
                                schemas.LinkSchema(
                                    url=afl.url.data,
                                    media_type=afl.media_type.data,
                                    relation=afl.relation.data,
                                    link_description=schemas.LocalizableDraftDescription(
                                        en=afl.link_description.en.data,
                                        pt=afl.link_description.pt.data,
                                    ),
                                )
                                for afl in af.asset_links.entries
                            ],
                        )
                        for af in creation_form.assets.entries
                    ],
                )
                logger.info(f"{to_create=}")

                yield ServerSentEventGenerator.patch_elements(
                    """<li>Creating survey-related record as a background task...</li>""",
                    selector="#feedback > ul",
                    mode=ElementPatchMode.APPEND,
                )

                enqueued_message: Message = tasks.create_survey_related_record.send(
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
                            "survey_related_records:detail",
                            survey_related_record_id=to_create.id,
                        )
                    ),
                    timeout_seconds=30,
                )
                async for sse_event in event_stream_generator:
                    yield sse_event

            else:
                logger.debug("form did not validate")
                template = template_processor.get_template(
                    "survey-related-records/create-form.html"
                )
                rendered = template.render(
                    request=request,
                    form=creation_form,
                    survey_mission_id=survey_mission_id,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector="#survey-related-record-create-form-container",
                    mode=ElementPatchMode.INNER,
                )

        return DatastarResponse(
            stream_events(), status_code=202 if form_is_valid else 422
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


@csrf_protect
async def add_create_survey_mission_form_link(request: Request):
    """Add a form link to a create_survey_mission form."""
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
    creation_form = await forms.SurveyMissionCreateForm.from_formdata(request)
    creation_form.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/create-form.html")
    rendered = template.render(
        form=creation_form,
        request=request,
        project=schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-mission-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


@csrf_protect
async def remove_create_survey_mission_form_link(request: Request):
    """Remove a form link from a create_survey_mission form."""
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
    create_survey_mission_form = await forms.SurveyMissionCreateForm.from_formdata(
        request
    )
    link_index = int(request.query_params.get("link_index", 0))
    create_survey_mission_form.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template("survey-missions/create-form.html")
    rendered = template.render(
        form=create_survey_mission_form,
        request=request,
        project=schemas.ProjectReadDetail.from_db_instance(project),
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-mission-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())
