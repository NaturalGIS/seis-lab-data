import html
import json
import logging
import typing

from datastar_py import ServerSentEventGenerator
from datastar_py.starlette import DatastarResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request

from ...db.queries import recordassets as asset_queries
from ...operations import projects as project_ops
from ...operations import surveymissions as mission_ops
from ...operations import surveyrelatedrecords as record_ops
from ...schemas import projects as project_schemas
from ...schemas import surveymissions as mission_schemas
from ...schemas import webui as webui_schemas
from .. import filters
from . import common

logger = logging.getLogger(__name__)


async def _event_streamer(target_datalist_id: str, values: typing.Sequence[str]):
    # values are names given by users, which may contain quotes or markup
    rendered = "".join(
        f'<option value="{html.escape(value)}"></option>' for value in values
    )
    yield ServerSentEventGenerator.patch_elements(
        f'<datalist id="{html.escape(target_datalist_id)}">{rendered}</datalist>',
    )


async def get_projects_datalist(request: Request) -> DatastarResponse:
    """Provides project names for building datalists.

    This route expects to be called via datastar @get and therefore tries
    to collect relevant signals from a "datastar" query param, which is a
    JSON object.
    """
    if (target_datalist_id := request.query_params.get("target")) is None:
        raise HTTPException(status_code=400, detail="target is required")
    if (datastar_signal := request.query_params.get("signal")) is None:
        raise HTTPException(status_code=400, detail="signal is required")
    try:
        search_value = json.loads(request.query_params.get("datastar"))[datastar_signal]
    except (TypeError, KeyError) as err:
        raise HTTPException(
            status_code=400, detail="Could not retrieve search value"
        ) from err
    name_filter = filters.NameFilter(value=search_value)
    internal_filter_kwargs = name_filter.as_kwargs()
    logger.debug(f"{internal_filter_kwargs=}")
    user = request.user if request.user.is_authenticated else None
    async with request.state.settings.get_db_session_maker()() as session:
        items, _ = await project_ops.list_projects(
            session,
            initiator=user,
            **internal_filter_kwargs,
        )
    serialized_items = [
        project_schemas.ProjectReadListItem.from_db_instance(item) for item in items
    ]
    return DatastarResponse(
        _event_streamer(
            target_datalist_id,
            [common.build_project_compound_name(request, i) for i in serialized_items],
        )
    )


async def get_missions_datalist(request: Request) -> DatastarResponse:
    """Provides survey mission names for building datalists.

    This route expects to be called via datastar @get and therefore tries
    to collect relevant signals from a "datastar" query param, which is a
    JSON object.

    A project given in the `filterProject` signal, as a compound name,
    restricts the suggestions to that project's survey missions. A search
    value which is itself a survey mission's compound name does not restrict
    the suggestions by name.
    """
    if (target_datalist_id := request.query_params.get("target")) is None:
        raise HTTPException(status_code=400, detail="target is required")
    if (datastar_signal := request.query_params.get("signal")) is None:
        raise HTTPException(status_code=400, detail="signal is required")
    try:
        signals = json.loads(request.query_params.get("datastar"))
        search_value = signals[datastar_signal]
    except (TypeError, KeyError) as err:
        raise HTTPException(
            status_code=400, detail="Could not retrieve search value"
        ) from err
    internal_filter_kwargs = {}
    try:
        filters.SurveyMissionCompoundNameFilter.from_params(
            {filters.SurveyMissionCompoundNameFilter.public_name: search_value}
        )
    except ValueError:
        internal_filter_kwargs.update(
            filters.NameFilter(value=search_value).as_kwargs()
        )
    try:
        internal_filter_kwargs.update(
            filters.ProjectCompoundNameFilter.from_params(signals).as_kwargs()
        )
    except ValueError:
        logger.debug("mission suggestions are not restricted to a project")
    logger.debug(f"{internal_filter_kwargs=}")
    user = request.user if request.user.is_authenticated else None
    async with request.state.settings.get_db_session_maker()() as session:
        items, _ = await mission_ops.list_survey_missions(
            session,
            initiator=user,
            **internal_filter_kwargs,
        )
    serialized_items = [
        mission_schemas.SurveyMissionReadListItem.from_db_instance(item)
        for item in items
    ]
    return DatastarResponse(
        _event_streamer(
            target_datalist_id,
            [common.build_mission_compound_name(request, i) for i in serialized_items],
        )
    )


async def get_records_datalist(request: Request) -> DatastarResponse:
    """Provides record names for building datalists.

    This route expects to be called via datastar @get and therefore tries
    to collect relevant signals from a "datastar" query param, which is a
    JSON object.
    """
    if (target_datalist_id := request.query_params.get("target")) is None:
        raise HTTPException(status_code=400, detail="target is required")
    if (datastar_signal := request.query_params.get("signal")) is None:
        raise HTTPException(status_code=400, detail="signal is required")
    try:
        search_value = json.loads(request.query_params.get("datastar"))[datastar_signal]
    except (TypeError, KeyError) as err:
        raise HTTPException(
            status_code=400, detail="Could not retrieve search value"
        ) from err
    name_filter = filters.NameFilter(value=search_value)
    internal_filter_kwargs = name_filter.as_kwargs()
    logger.debug(f"{internal_filter_kwargs=}")
    user = request.user if request.user.is_authenticated else None
    async with request.state.settings.get_db_session_maker()() as session:
        items, _ = await record_ops.list_survey_related_records(
            session,
            initiator=user,
            **internal_filter_kwargs,
        )
    serialized_items = [
        webui_schemas.SurveyRelatedRecordReadListItem.from_db_instance(item)
        for item in items
    ]
    return DatastarResponse(
        _event_streamer(
            target_datalist_id,
            [
                common.build_related_record_compound_name(request, i)
                for i in serialized_items
            ],
        )
    )


async def get_registered_media_types(request: Request) -> DatastarResponse:
    """Provides existing media_types for building datalists.

    This route expects to be called via datastar @get and therefore tries
    to collect relevant signals from a "datastar" query param, which is a
    JSON object.
    """
    if (target_datalist_id := request.query_params.get("target")) is None:
        raise HTTPException(status_code=400, detail="target is required")
    try:
        search_value = json.loads(request.query_params.get("datastar")).get(
            "filterMediaType"
        )
    except (TypeError, KeyError) as err:
        raise HTTPException(
            status_code=400, detail="Could not retrieve search value"
        ) from err
    async with request.state.settings.get_db_session_maker()() as session:
        media_types = await asset_queries.list_media_types(
            session, name_filter=search_value
        )
    return DatastarResponse(
        _event_streamer(target_datalist_id, [i for i in media_types if i])
    )
