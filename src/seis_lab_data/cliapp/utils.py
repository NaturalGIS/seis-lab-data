import tomllib

import httpx
from anyio import Path

from .. import (
    authentik,
    config,
    constants,
)
from ..db.commands import users as user_commands
from ..schemas import (
    datasetcategories as category_schemas,
    discovery as discovery_schemas,
    identifiers,
    user as user_schemas,
    workflowstages as stage_schemas,
)


async def parse_bootstrap_data_path(data_path: Path) -> dict:
    return tomllib.loads(await data_path.read_text())


async def get_bootstrap_data(
    data_path: Path,
) -> dict[
    constants.ResourceType,
    list[
        category_schemas.DatasetCategoryCreate
        | discovery_schemas.AssetDiscoveryConfigurationCreate
        | stage_schemas.WorkflowStageCreate
    ],
]:
    parsed = await parse_bootstrap_data_path(data_path)
    return {
        constants.ResourceType.CATEGORY: [
            category_schemas.DatasetCategoryCreate(**i)
            for i in parsed.get("dataset_categories", [])
        ],
        constants.ResourceType.WORKFLOW_STAGE: [
            stage_schemas.WorkflowStageCreate(**i)
            for i in parsed.get("workflow_stages", [])
        ],
        constants.ResourceType.ASSET_DISCOVERY_CONFIG: [
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=i["id"],
                name=i["name"],
                media_type=i["media_type"],
                relative_path_regexp=i["relative_path_regexp"],
                workflow_stage_id=i["workflow_stage"],
                dataset_category_id=i["dataset_category"],
            )
            for i in parsed.get("asset_discovery_configurations", [])
        ],
    }


async def resolve_admin_user(
    settings: config.SeisLabDataSettings,
    admin_username: str | None = None,
    admin_user_id: str | None = None,
) -> user_schemas.User:
    async with httpx.AsyncClient() as client:
        if admin_user_id:
            user = await authentik.get_user_by_uuid(
                admin_token=settings.auth_admin_token,
                user_id=identifiers.UserId(admin_user_id),
                web_client=client,
                authentik_base_url=settings.auth_internal_base_url,
            )
            identifier = admin_user_id
        elif admin_username:
            user = await authentik.get_user_by_username(
                admin_token=settings.auth_admin_token,
                username=admin_username,
                web_client=client,
                authentik_base_url=settings.auth_internal_base_url,
            )
            identifier = admin_username
        else:
            raise ValueError("Either admin_user_id or admin_username must be provided.")
    if user is None:
        raise ValueError(f"User {identifier!r} not found in Authentik.")
    async with settings.get_db_session_maker()() as session:
        await user_commands.upsert_user(session, user)
    return user
