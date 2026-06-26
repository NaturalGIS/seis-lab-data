import dataclasses
import json
import logging
import uuid

from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.starlette import DatastarResponse
from starlette.endpoints import HTTPEndpoint
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette_babel import gettext_lazy as _
from starlette_wtf import csrf_protect

from ... import (
    config,
    constants,
    subscribers,
)
from ...db.queries import discovery as discovery_queries
from ...permissions import discovery as discovery_permissions
from ...schemas import (
    discovery as discovery_schemas,
    identifiers,
    webui as webui_schemas,
)
from ...tasks import discovery as discovery_tasks
from .. import (
    filters,
)
from ..forms import discovery as discovery_forms
from ..streamhandlers import discovery as discovery_handlers
from .auth import requires_auth
from .common import (
    get_page_from_request_params,
    get_pagination_info,
)

logger = logging.getLogger(__name__)


async def get_list_component(request: Request): ...


@csrf_protect
@requires_auth
async def get_creation_form(request: Request):
    """Return a form suitable for creating a new asset_discovery_configuration."""
    form_instance = (
        await discovery_forms.AssetDiscoveryConfigurationCreateForm.from_request(
            request
        )
    )
    form_instance.request_id.data = str(identifiers.RequestId(uuid.uuid4()))
    template_processor: Jinja2Templates = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "discovery/create-form-page.html",
        context={
            "form": form_instance,
            "breadcrumbs": [
                webui_schemas.BreadcrumbItem(
                    name=_("Home"), url=request.url_for("home")
                ),
                webui_schemas.BreadcrumbItem(
                    name=_("Asset discovery configurations"),
                    url=request.url_for("asset_discovery_configurations:list"),
                ),
                webui_schemas.BreadcrumbItem(
                    name=_("New asset discovery configuration")
                ),
            ],
        },
    )


@csrf_protect
@requires_auth
async def get_update_form(request: Request): ...


async def stream_to_list_page(request: Request):
    subscription = subscribers.subscribe_to_topic(
        request.state.redis_client,
        constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
        subscribers.AssetDiscoveryConfigurationHandlerContext(
            jinja_environment=request.state.templates.env,
            url_resolver=request.url_for,
            db_session_factory=request.state.settings.get_db_session_maker(),
        ),
        {
            "asset_discovery_configuration_created": discovery_handlers.handle_list_page_asset_discovery_configuration_modification,
            "asset_discovery_configuration_updated": discovery_handlers.handle_list_page_asset_discovery_configuration_modification,
            "asset_discovery_configuration_deleted": discovery_handlers.handle_list_page_asset_discovery_configuration_modification,
        },
    )

    async def event_streamer():
        async for sse_event in subscription:
            yield sse_event

    return DatastarResponse(event_streamer(), status_code=200)


@requires_auth
async def stream_to_new_page(request: Request):
    """Stream relevant updates for the new asset_discovery_configuration page."""
    try:
        request_id = identifiers.RequestId(uuid.UUID(request.path_params["request_id"]))
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid request id") from err

    # TODO: should we update the form fields with handlers too?
    subscription = subscribers.subscribe_to_topic(
        request.state.redis_client,
        constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
        subscribers.AssetDiscoveryConfigurationHandlerContext(
            request_id=request_id,
            user=request.user,
            url_resolver=request.url_for,
            jinja_environment=request.state.templates.env,
            db_session_factory=request.state.settings.get_db_session_maker(),
        ),
        {
            "asset_discovery_configuration_created": discovery_handlers.handle_new_page_asset_discovery_configuration_creation_successful,
            "asset_discovery_configuration_not_created": discovery_handlers.handle_new_page_asset_discovery_configuration_creation_failed,
        },
    )

    async def event_streamer():
        async for sse_event in subscription:
            yield sse_event

    return DatastarResponse(event_streamer())


@requires_auth
async def stream_to_update_page(request: Request): ...


class AssetDiscoveryConfigurationCollectionEndpoint(HTTPEndpoint):
    async def get(self, request: Request):
        settings: config.SeisLabDataSettings = request.state.settings
        user = request.user if request.user.is_authenticated else None
        current_page = get_page_from_request_params(request)
        current_language = request.state.language
        list_filters = filters.AssetDiscoveryConfigurationListFilters.from_params(
            request.query_params, current_language
        )
        async with settings.get_db_session_maker()() as session:
            (
                items,
                num_total,
            ) = await discovery_queries.list_asset_discovery_configurations(
                session,
                page=current_page,
                page_size=settings.pagination_page_size,
                include_total=True,
                **list_filters.as_kwargs(),
            )
            num_unfiltered_total = (
                await discovery_queries.list_asset_discovery_configurations(
                    session, include_total=True
                )
            )[1]
        template_processor = request.state.templates
        pagination_info = get_pagination_info(
            current_page=current_page,
            page_size=settings.pagination_page_size,
            total_filtered_items=num_total,
            total_unfiltered_items=num_unfiltered_total,
            collection_url=str(request.url_for("asset_discovery_configurations:list")),
        )

        serialized_items = [
            discovery_schemas.AssetDiscoveryConfigurationReadDetail.from_db_instance(i)
            for i in items
        ]
        return template_processor.TemplateResponse(
            request,
            "discovery/list.html",
            context={
                "items": serialized_items,
                "pagination": pagination_info,
                "breadcrumbs": [
                    webui_schemas.BreadcrumbItem(
                        name=_("Home"), url=request.url_for("home")
                    ),
                    webui_schemas.BreadcrumbItem(
                        name=_("Asset Discovery Configurations")
                    ),
                ],
                "user_can_create": discovery_permissions.can_create_asset_discovery_configuration(
                    user
                )
                if user is not None
                else False,
                "search_initial_value": list_filters.get_text_search_filter(
                    current_language
                ),
            },
        )

    @csrf_protect
    @requires_auth
    async def post(self, request: Request):
        """Create a new asset_discovery_configuration."""
        template_processor: Jinja2Templates = request.state.templates
        user = request.user
        form_instance = await discovery_forms.AssetDiscoveryConfigurationCreateForm.get_validated_form_instance(
            request
        )
        if form_instance.has_validation_errors():
            logger.debug("form did not validate")

            async def validation_event_streamer():
                template = template_processor.get_template("discovery/create-form.html")
                rendered = template.render(
                    request=request,
                    form=form_instance,
                )
                yield ServerSentEventGenerator.patch_elements(
                    rendered,
                    selector=webui_schemas.selector_info.main_content_selector,
                    mode=ElementPatchMode.INNER,
                )
                yield ServerSentEventGenerator.execute_script(
                    "document.querySelector('.is-invalid')?.scrollIntoView({behavior: 'smooth', block: 'center'})"
                )

            # Datastar only processes SSE streams from 2xx responses; non-2xx are treated as errors
            return DatastarResponse(validation_event_streamer(), status_code=200)

        to_create = discovery_schemas.AssetDiscoveryConfigurationCreate(
            id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
            name=form_instance.name.data,
            relative_path_regexp=form_instance.relative_path_regexp.data,
            dataset_category_id=form_instance.dataset_category_id.data,
            workflow_stage_id=form_instance.workflow_stage_id.data,
        )
        request_id = identifiers.RequestId(uuid.UUID(form_instance.request_id.data))
        discovery_tasks.create_asset_discovery_configuration.send(
            raw_request_id=str(request_id),
            raw_to_create=to_create.model_dump_json(),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )  # noqa
        return Response(status_code=200)


routes = [
    Route("/", AssetDiscoveryConfigurationCollectionEndpoint, name="list"),
    Route("/stream", stream_to_list_page, name="list_stream"),
    Route("/search", get_list_component, name="get_list_component"),
    Route(
        "/new",
        get_creation_form,
        methods=["GET"],
        name="get_creation_form",
    ),
    Route(
        "/new/{request_id}/stream",
        stream_to_new_page,
        methods=["GET"],
        name="new_stream",
    ),
    Route(
        "/{asset_discovery_configuration_id}/update",
        get_update_form,
        methods=["GET"],
        name="get_update_form",
    ),
    Route(
        "/{asset_discovery_configuration_id}/update/stream/{request_id}",
        stream_to_update_page,
        methods=["GET"],
        name="update_stream",
    ),
]
