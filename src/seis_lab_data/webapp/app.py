import contextlib
from collections.abc import Callable
from typing import (
    AsyncIterator,
    TypedDict,
)

import jinja2
from authlib.integrations.starlette_client import OAuth
from redis import asyncio as aioredis
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.applications import Starlette
from starlette_babel.contrib.jinja import configure_jinja_env
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import (
    Mount,
    Route,
)
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette_babel import (
    get_translator,
    LocaleMiddleware,
)
from starlette_wtf import CSRFProtectMiddleware

from .. import (
    config,
    events,
)
from ..auth import (
    AuthConfig,
    get_oauth_manager,
)
from ..db.engine import (
    get_engine,
    get_session_maker,
)
from ..processing.broker import setup_broker

from . import routes
from .jinjafilters import (
    translate_enum,
    translate_localizable_string,
)


class State(TypedDict):
    settings: config.SeisLabDataSettings
    templates: Jinja2Templates
    auth_config: AuthConfig
    oauth_manager: OAuth
    session_maker: Callable[[], AsyncSession]
    event_emitter: events.EventEmitterProtocol
    redis_client: aioredis.Redis


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    settings = config.get_settings()
    auth_config = AuthConfig.from_settings(settings)
    shared_translator = get_translator()
    shared_translator.load_from_directory(settings.translations_dir)
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(settings.templates_dir), autoescape=True
    )
    jinja_env.filters["translate_localizable_string"] = translate_localizable_string
    jinja_env.filters["translate_enum"] = translate_enum
    configure_jinja_env(jinja_env)
    templates = Jinja2Templates(env=jinja_env)
    engine = get_engine(settings.database_dsn.unicode_string(), settings.debug)
    yield State(
        settings=settings,
        templates=templates,
        auth_config=auth_config,
        oauth_manager=get_oauth_manager(auth_config),
        session_maker=get_session_maker(engine),
        event_emitter=events.get_event_emitter(settings),
        redis_client=aioredis.from_url(settings.message_broker_dsn.unicode_string()),
    )
    await engine.dispose()


def create_app_from_settings(settings: config.SeisLabDataSettings) -> Starlette:
    setup_broker(settings)
    app = Starlette(
        debug=settings.debug,
        routes=[
            Route("/", routes.home),
            Route("/login", routes.login),
            Route("/oauth2/callback", routes.auth_callback),
            Route("/logout", routes.logout),
            Route("/profile", routes.profile),
            Route("/protected", routes.protected),
            Route("/set-language/{lang}", routes.set_language, name="set_language"),
            Mount(
                "/projects",
                name="projects",
                routes=[
                    Route("/", routes.ProjectCollectionEndpoint, name="list"),
                    Route(
                        "/new/add-form-link",
                        routes.add_create_project_form_link,
                        methods=["POST"],
                        name="add_form_link",
                    ),
                    Route(
                        "/new/remove-form-link",
                        routes.remove_create_project_form_link,
                        methods=["POST"],
                        name="remove_form_link",
                    ),
                    Route(
                        "/new",
                        routes.get_project_creation_form,
                        methods=["GET"],
                        name="get_creation_form",
                    ),
                    Route(
                        "/{project_id}/update",
                        routes.get_project_update_form,
                        methods=["GET"],
                        name="get_update_form",
                    ),
                    Route(
                        "/{project_id}/add-update-form-link",
                        routes.add_update_project_form_link,
                        methods=["POST"],
                        name="add_update_form_link",
                    ),
                    Route(
                        "/{project_id}/remove-update-form-link",
                        routes.remove_update_project_form_link,
                        methods=["POST"],
                        name="remove_update_form_link",
                    ),
                    Route(
                        "/{project_id}/details",
                        routes.get_project_details_component,
                        methods=["GET"],
                        name="get_details_component",
                    ),
                    Route(
                        "/{project_id}",
                        routes.ProjectDetailEndpoint,
                        name="detail",
                    ),
                ],
            ),
            Mount(
                "/survey-missions",
                name="survey_missions",
                routes=[
                    Route(
                        "/",
                        routes.SurveyMissionCollectionEndpoint,
                        methods=["GET"],
                        name="list",
                    ),
                    Route(
                        "/{project_id}/new",
                        routes.get_survey_mission_creation_form,
                        methods=["GET"],
                        name="get_creation_form",
                    ),
                    Route(
                        "/{project_id}/new/add-form-link",
                        routes.add_create_survey_mission_form_link,
                        methods=["POST"],
                        name="add_form_link",
                    ),
                    Route(
                        "/{project_id}/new/remove-form-link",
                        routes.remove_create_survey_mission_form_link,
                        methods=["POST"],
                        name="remove_form_link",
                    ),
                    Route(
                        "/{survey_mission_id}",
                        routes.SurveyMissionDetailEndpoint,
                        name="detail",
                    ),
                ],
            ),
            Mount(
                "/survey-related-records",
                name="survey_related_records",
                routes=[
                    Route(
                        "/",
                        routes.SurveyRelatedRecordCollectionEndpoint,
                        methods=["GET"],
                        name="list",
                    ),
                    Route(
                        "/{survey_mission_id}/new",
                        routes.get_survey_related_record_creation_form,
                        methods=["GET"],
                        name="get_creation_form",
                    ),
                    Route(
                        "/{survey_mission_id}/new/add-form-link",
                        routes.add_create_survey_related_record_form_link,
                        methods=["POST"],
                        name="add_form_link",
                    ),
                    Route(
                        "/{survey_mission_id}/new/remove-form-link",
                        routes.remove_create_survey_related_record_form_link,
                        methods=["POST"],
                        name="remove_form_link",
                    ),
                    Route(
                        "/{survey_mission_id}/new/add-asset-form",
                        routes.add_create_survey_related_record_form_asset,
                        methods=["POST"],
                        name="add_asset_form",
                    ),
                    Route(
                        "/{survey_mission_id}/new/remove-asset-form",
                        routes.remove_create_survey_related_record_form_asset,
                        methods=["POST"],
                        name="remove_asset_form",
                    ),
                    Route(
                        "/{survey_mission_id}/new/add-asset-link-form/{asset_index}",
                        routes.add_create_survey_related_record_form_asset_link,
                        methods=["POST"],
                        name="add_asset_link_form",
                    ),
                    Route(
                        "/{survey_mission_id}/new/remove-asset-link-form/{asset_index}",
                        routes.remove_create_survey_related_record_form_asset_link,
                        methods=["POST"],
                        name="remove_asset_link_form",
                    ),
                    Route(
                        "/{survey_related_record_id}",
                        routes.SurveyRelatedRecordDetailEndpoint,
                        name="detail",
                    ),
                ],
            ),
        ],
        lifespan=lifespan,
        middleware=[
            Middleware(
                LocaleMiddleware,
                locales=settings.locales,
                default_locale=settings.locales[0],
            ),
            Middleware(
                SessionMiddleware,
                secret_key=settings.session_secret_key,
            ),
            Middleware(
                CSRFProtectMiddleware,
                csrf_secret=settings.csrf_secret,
            ),
        ],
    )
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    return app


def create_app() -> Starlette:
    settings = config.get_settings()
    return create_app_from_settings(settings)
