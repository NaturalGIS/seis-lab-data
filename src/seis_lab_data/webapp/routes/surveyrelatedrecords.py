import dataclasses
import json
import logging
from typing import (
    AsyncGenerator,
    TypeVar,
)
import uuid

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.sse import DatastarEvent
from datastar_py.starlette import DatastarResponse
from dramatiq import Message
from jinja2 import Template
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
from ...db import (
    models,
    queries,
)
from ...processing import tasks
from .. import forms
from .auth import (
    get_user,
    fancy_requires_auth,
)
from .common import (
    get_id_from_request_path,
    get_pagination_info,
    produce_event_stream_for_topic,
)

logger = logging.getLogger(__name__)


_SELECTOR_INFO = schemas.ItemSelectorInfo(
    feedback="[aria-label='feedback-messages'] > ul",
    item_details="[aria-label='survey-mission-details']",
    item_name="[aria-label='survey-mission-name']",
    breadcrumbs="[aria-label='breadcrumbs']",
)


async def _get_survey_related_record_details(
    request: Request,
) -> schemas.SurveyRelatedRecordDetails:
    """Utility function to get survey-related record details and its assets."""
    try:
        current_page = int(request.query_params.get("page", 1))
        if current_page < 1:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid page number")

    user = get_user(request.session.get("user", {}))
    settings: config.SeisLabDataSettings = request.state.settings
    session_maker = request.state.session_maker
    survey_related_record_id = get_id_from_request_path(
        request, "survey_related_record_id", schemas.SurveyRelatedRecordId
    )
    async with session_maker() as session:
        try:
            survey_related_record = await operations.get_survey_related_record(
                survey_related_record_id,
                user.id if user else None,
                session,
                request.state.settings,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if survey_related_record is None:
            raise HTTPException(
                status_code=404,
                detail=_(
                    f"Survey-related record {survey_related_record_id!r} not found."
                ),
            )
    serialized = schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        survey_related_record
    )
    can_update = await permissions.can_update_survey_related_record(
        user, survey_related_record_id, settings=settings
    )
    return schemas.SurveyRelatedRecordDetails(
        item=serialized,
        permissions=schemas.UserPermissionDetails(
            can_create_children=can_update,
            can_update=can_update,
            can_delete=await permissions.can_delete_survey_related_record(
                user, survey_related_record_id, settings=settings
            ),
        ),
        breadcrumbs=[
            schemas.BreadcrumbItem(name=_("Home"), url=str(request.url_for("home"))),
            schemas.BreadcrumbItem(
                name=_("Projects"), url=str(request.url_for("projects:list"))
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.survey_mission.project.name["en"]),
                url=str(
                    request.url_for(
                        "projects:detail",
                        project_id=survey_related_record.survey_mission.project.id,
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.survey_mission.name["en"]),
                url=str(
                    request.url_for(
                        "survey_missions:detail",
                        project_id=survey_related_record.survey_mission.id,
                    )
                ),
            ),
            schemas.BreadcrumbItem(
                name=str(survey_related_record.name["en"]),
            ),
        ],
    )


@fancy_requires_auth
async def get_survey_related_record_details_component(request: Request):
    details = await _get_survey_related_record_details(request)
    template_processor = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/detail-component.html"
    )
    rendered = template.render(
        request=request,
        survey_related_record=details.item,
        permissions=details.permissions,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector=_SELECTOR_INFO.item_details,
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


FormType = TypeVar(
    "FormType",
    bound=forms.FormProtocol,
)


async def _build_form_instance(request: Request, form_type: type[FormType]) -> FormType:
    form_instance = await form_type.from_formdata(request)
    current_language = request.state.language
    async with request.state.session_maker() as session:
        form_instance.dataset_category_id.choices = [
            (dc.id, dc.name.get(current_language, dc.name["en"]))
            for dc in await queries.collect_all_dataset_categories(
                session,
                order_by_clause=models.DatasetCategory.name[current_language].astext,
            )
        ]
        form_instance.domain_type_id.choices = [
            (dt.id, dt.name.get(current_language, dt.name["en"]))
            for dt in await queries.collect_all_domain_types(
                session,
                order_by_clause=models.DomainType.name[current_language].astext,
            )
        ]
        form_instance.workflow_stage_id.choices = [
            (ws.id, ws.name.get(current_language, ws.name["en"]))
            for ws in await queries.collect_all_workflow_stages(
                session,
                order_by_clause=models.WorkflowStage.name[current_language].astext,
            )
        ]
    return form_instance


async def _get_parent_survey_mission(request: Request) -> models.SurveyMission:
    user = get_user(request.session.get("user", {}))
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    async with request.state.session_maker() as session:
        if not (
            survey_mission := await operations.get_survey_mission(
                parent_survey_mission_id, user, session, request.state.settings
            )
        ):
            raise HTTPException(
                404, _(f"Survey mission with id {parent_survey_mission_id} not found.")
            )
    return survey_mission


@csrf_protect
@fancy_requires_auth
async def get_survey_related_record_creation_form(request: Request):
    """Get survey-related record creation form."""
    parent_survey_mission = await _get_parent_survey_mission(request)
    survey_mission_id = schemas.SurveyMissionId(parent_survey_mission.id)
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )

    template_processor: Jinja2Templates = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-related-records/create.html",
        context={
            "form": form_instance,
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
                    name=str(parent_survey_mission.project.name["en"]),
                    url=request.url_for(
                        "projects:detail",
                        project_id=schemas.ProjectId(parent_survey_mission.project.id),
                    ),
                ),
                schemas.BreadcrumbItem(
                    name=str(parent_survey_mission.name["en"]),
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


@csrf_protect
async def add_create_survey_related_record_form_asset_link(request: Request):
    """Add an asset link form to a create_survey_related_record form."""
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    asset_index = int(request.path_params["asset_index"])
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )
    form_instance.assets[asset_index].asset_links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
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
    survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )

    asset_index = int(request.path_params["asset_index"])
    link_index = int(request.query_params.get("link_index", 0))

    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )

    form_instance.assets[asset_index].asset_links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
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
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )
    form_instance.assets.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
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
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )
    asset_index = int(request.query_params.get("asset_index", 0))
    form_instance.assets.entries.pop(asset_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
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
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )
    form_instance.links.append_entry()
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
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
    parent_survey_mission_id = get_id_from_request_path(
        request, "survey_mission_id", schemas.SurveyMissionId
    )
    form_instance = await _build_form_instance(
        request, forms.SurveyRelatedRecordCreateForm
    )
    link_index = int(request.query_params.get("link_index", 0))
    form_instance.links.entries.pop(link_index)
    template_processor: Jinja2Templates = request.state.templates
    template = template_processor.get_template(
        "survey-related-records/create-form.html"
    )
    rendered = template.render(
        form=form_instance,
        request=request,
        survey_mission_id=parent_survey_mission_id,
    )

    async def event_streamer():
        yield ServerSentEventGenerator.patch_elements(
            rendered,
            selector="#survey-related-record-create-form-container",
            mode=ElementPatchMode.INNER,
        )

    return DatastarResponse(event_streamer())


# TODO: remove this function and use _build_form_instance() and _get_parent_survey_mission() instead
async def generate_survey_related_record_creation_form(
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


class SurveyRelatedRecordCollectionEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        """List survey-related records."""
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
            items, num_total = await operations.list_survey_related_records(
                session,
                initiator=user.id if user else None,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
            )
            num_unfiltered_total = (
                await operations.list_survey_related_records(
                    session, initiator=user or None, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page,
            settings.pagination_page_size,
            num_total,
            num_unfiltered_total,
            collection_url=str(request.url_for("survey_related_records:list")),
        )
        return template_processor.TemplateResponse(
            request,
            "survey-related-records/list.html",
            context={
                "items": [
                    schemas.SurveyRelatedRecordReadListItem.from_db_instance(item)
                    for item in items
                ],
                "pagination": pagination_info,
                "breadcrumbs": [
                    schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                    schemas.BreadcrumbItem(name=_("Survey-related records")),
                ],
            },
        )


class SurveyRelatedRecordDetailEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        """Get survey-related record details."""
        details = await _get_survey_related_record_details(request)
        template_processor = request.state.templates
        return template_processor.TemplateResponse(
            request,
            "survey-related-records/detail.html",
            context={
                "survey_related_record": details.item,
                "permissions": details.permissions,
                "breadcrumbs": details.breadcrumbs,
            },
        )

    @csrf_protect
    @fancy_requires_auth
    async def delete(self, request: Request):
        survey_related_record_id = get_id_from_request_path(
            request, "survey_related_record_id", schemas.SurveyRelatedRecordId
        )
        session_maker = request.state.session_maker
        user = get_user(request.session.get("user", {}))
        async with session_maker() as session:
            if (
                survey_related_record := await operations.get_survey_related_record(
                    survey_related_record_id,
                    user.id if user else None,
                    session,
                    request.state.settings,
                )
                is None
            ):
                raise HTTPException(
                    status_code=404,
                    detail=_(
                        f"Survey-related record {survey_related_record_id!r} not found."
                    ),
                )

        request_id = schemas.RequestId(uuid.uuid4())

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    status=final_message.status.value, message=final_message.message
                ),
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.APPEND,
            )
            yield ServerSentEventGenerator.redirect(
                str(
                    request.url_for(
                        "survey_missions:detail",
                        survey_mission_id=survey_related_record.survey_mission_id,
                    )
                )
            )

        async def handle_processing_failure(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            yield ServerSentEventGenerator.patch_elements(
                message_template.render(
                    status=final_message.status.value,
                    message=f"ERROR: {final_message.message}",
                ),
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.APPEND,
            )

        async def stream_events():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Deleting survey-related record as a background task...</li>""",
                selector="#feedback > ul",
                mode=ElementPatchMode.APPEND,
            )
            enqueued_message: Message = tasks.delete_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_survey_related_record_id=str(survey_related_record_id),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=f"progress:{request_id}",
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(stream_events())

    @csrf_protect
    @fancy_requires_auth
    async def put(self, request: Request):
        """Update an existing survey-related record."""
        template_processor: Jinja2Templates = request.state.templates
        user = get_user(request.session.get("user", {}))
        session_maker = request.state.session_maker
        survey_related_record_id = get_id_from_request_path(
            request, "survey_related_record_id", schemas.SurveyRelatedRecordId
        )
        async with session_maker() as session:
            if (
                survey_related_record := await operations.get_survey_related_record(
                    survey_related_record_id, user, session, request.state.settings
                )
            ) is None:
                raise HTTPException(
                    404,
                    f"Survey-related record {survey_related_record_id!r} not found.",
                )

        parent_survey_mission_id = schemas.SurveyMissionId(
            survey_related_record.survey_mission_id
        )
        form_instance = (
            await forms.SurveyRelatedRecordUpdateForm.get_validated_form_instance(
                request,
                survey_mission_id=parent_survey_mission_id,
                disregard_id=survey_related_record_id,
            )
        )
        logger.debug(f"{form_instance.has_validation_errors()=}")

        if form_instance.has_validation_errors():
            logger.debug("form did not validate")
            logger.debug(f"{form_instance.errors=}")

            async def stream_validation_failed_events():
                template = template_processor.get_template(
                    "survey-related-records/update-form.html"
                )
                rendered = template.render(
                    request=request,
                    survey_related_record=survey_related_record,
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=_SELECTOR_INFO.item_details,
                    mode=ElementPatchMode.INNER,
                )

            return DatastarResponse(stream_validation_failed_events(), status_code=422)

        request_id = schemas.RequestId(uuid.uuid4())
        to_update = schemas.SurveyRelatedRecordUpdate(
            owner=user.id,
            survey_mission_id=parent_survey_mission_id,
            name=schemas.LocalizableDraftName(
                en=form_instance.name.en.data,
                pt=form_instance.name.pt.data,
            ),
            description=schemas.LocalizableDraftDescription(
                en=form_instance.description.en.data,
                pt=form_instance.description.pt.data,
            ),
            dataset_category_id=form_instance.dataset_category_id.data,
            domain_type_id=form_instance.domain_type_id.data,
            workflow_stage_id=form_instance.workflow_stage_id.data,
            relative_path=form_instance.relative_path.data,
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
                for lf in form_instance.links.entries
            ],
            assets=[
                schemas.RecordAssetUpdate(
                    id=schemas.RecordAssetId(uuid.UUID(af.asset_id.data)),
                    name=schemas.LocalizableDraftName(
                        en=af.name.en.data,
                        pt=af.name.pt.data,
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en=af.description.en.data,
                        pt=af.description.pt.data,
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
                        for afl in af.links.entries
                    ],
                )
                for af in form_instance.assets.entries
            ],
        )

        async def handle_processing_success(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            """Handle successful processing of the survey-related record update background task.

            After receiving the final message with a success status, update the
            UI to reflect the changes.
            """
            details = await _get_survey_related_record_details(request)
            rendered_message = message_template.render(
                status=final_message.status.value,
                message=final_message.message,
            )
            yield ServerSentEventGenerator.patch_elements(
                rendered_message,
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.APPEND,
            )
            template = template_processor.get_template(
                "survey-related-records/detail-component.html"
            )
            # need to update:
            # - survey-related record details section (name, description, links, ...)
            # - breadcrumbs (record's name may have changed)
            # - page title (record's name may have changed)
            # - clear the feedback section
            breadcrumbs_template = template_processor.get_template("breadcrumbs.html")
            yield ServerSentEventGenerator.patch_elements(
                breadcrumbs_template.render(
                    request=request, breadcrumbs=details.breadcrumbs
                ),
                selector=_SELECTOR_INFO.breadcrumbs,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                template.render(
                    request=request,
                    survey_related_record=details.item,
                    permissions=details.permissions,
                ),
                selector=_SELECTOR_INFO.item_details,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                details.item.name.en,
                selector=_SELECTOR_INFO.item_name,
                mode=ElementPatchMode.INNER,
            )
            yield ServerSentEventGenerator.patch_elements(
                "",
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.INNER,
            )

        async def handle_processing_failure(
            final_message: schemas.ProcessingMessage, message_template: Template
        ) -> AsyncGenerator[DatastarEvent, None]:
            rendered = message_template.render(
                status=final_message.status.value,
                message=f"ERROR: {final_message.message}",
            )
            yield ServerSentEventGenerator.patch_elements(
                rendered,
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.APPEND,
            )

        async def event_streamer():
            yield ServerSentEventGenerator.patch_elements(
                """<li>Updating survey-related record as a background task...</li>""",
                selector=_SELECTOR_INFO.feedback,
                mode=ElementPatchMode.APPEND,
            )

            enqueued_message: Message = tasks.update_survey_related_record.send(
                raw_request_id=str(request_id),
                raw_survey_related_record_id=str(survey_related_record_id),
                raw_to_update=to_update.model_dump_json(exclude_unset=True),
                raw_initiator=json.dumps(dataclasses.asdict(user)),
            )
            logger.debug(f"{enqueued_message=}")
            redis_client: Redis = request.state.redis_client
            event_stream_generator = produce_event_stream_for_topic(
                redis_client,
                request,
                topic_name=f"progress:{request_id}",
                on_success=handle_processing_success,
                on_failure=handle_processing_failure,
                timeout_seconds=30,
            )
            async for sse_event in event_stream_generator:
                yield sse_event

        return DatastarResponse(event_streamer(), status_code=202)
