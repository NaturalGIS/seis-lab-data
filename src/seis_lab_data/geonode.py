"""Facilities for dealing with the GeoNode API (v2), as used by GeoNode v5."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx

from . import constants
from .errors import SeisLabDataError

logger = logging.getLogger(__name__)


class GeoNodeError(SeisLabDataError):
    pass


def get_upload_files(data_path: Path) -> dict[str, Path]:
    """Map the GeoNode upload form fields to the files to send in them.

    Shapefiles are sent along with their sidecars, which share the file's stem,
    e.g. FOO.shp -> FOO.dbf - GeoNode cannot import a shapefile without them.
    """
    files = {"base_file": data_path}
    if data_path.suffix.lower() == ".shp":
        sidecars = {
            path.suffix.lower(): path
            for path in data_path.parent.glob(f"{data_path.stem}.*")
            if path.is_file()
        }
        for suffix, field_name in constants.GEONODE_SHAPEFILE_SIDECAR_FIELDS.items():
            if (sidecar := sidecars.get(suffix)) is not None:
                files[field_name] = sidecar
    return files


def upload_dataset(
    api_url: str,
    token: str,
    files: dict[str, Path],
    resource_pk: int | None = None,
) -> str:
    """Upload a dataset to GeoNode, returning the id of the import's execution.

    When `resource_pk` is given the upload replaces the data of that existing
    GeoNode resource, otherwise a new resource is created.

    sync and slow: the files are streamed out from disk, async callers must run
    this in a worker thread.
    """
    form_data = (
        {"action": "replace", "resource_pk": str(resource_pk)}
        if resource_pk is not None
        else {"action": "upload"}
    )
    opened = {field_name: path.open("rb") for field_name, path in files.items()}
    try:
        with httpx.Client(
            base_url=api_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(30, write=None),
        ) as client:
            response = client.post(
                "/api/v2/uploads/upload",
                data=form_data,
                files={
                    field_name: (files[field_name].name, file_obj)
                    for field_name, file_obj in opened.items()
                },
            )
    finally:
        for file_obj in opened.values():
            file_obj.close()
    if not response.is_success:
        raise GeoNodeError(
            f"GeoNode rejected the upload ({response.status_code}): {response.text}"
        )
    return response.json()["execution_id"]


async def watch_execution(
    client: httpx.AsyncClient,
    execution_id: str,
    poll_interval_seconds: float = constants.GEONODE_EXECUTION_POLL_INTERVAL_SECONDS,
) -> AsyncGenerator[dict, None]:
    """Poll an import's execution request, yielding it whenever its step changes.

    The last yielded execution request is the finished one, its output params
    hold the resulting resource's id. Raises if the execution fails.
    """
    last_step = None
    while True:
        response = await client.get(f"/api/v2/executionrequest/{execution_id}")
        response.raise_for_status()
        execution = response.json()["request"]
        match execution["status"]:
            case "finished":
                yield execution
                return
            case "failed":
                raise GeoNodeError(
                    f"GeoNode failed to import the dataset: {execution.get('log')}"
                )
        if execution.get("step") != last_step:
            last_step = execution.get("step")
            yield execution
        await asyncio.sleep(poll_interval_seconds)
