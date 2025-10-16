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
from starlette_wtf import (
    CSRFProtectMiddleware,
    csrf_token,
)

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

from .routes import (
    auth,
    base,
)
from .routes.projects import routes as projects_routes
from .routes.surveymissions import routes as missions_routes
from .routes.surveyrelatedrecords import routes as records_routes
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
    jinja_env.globals.update(
        {
            "csrf_token": csrf_token,
            "icons": {
                "delete_item": "delete",
                "edit_item": "edit",
                "new_item": "add_circle_outline",
                "projects": "view_timeline",
                "survey_missions": "directions_boat",
                "survey_related_records": "source",
                "view_details": "info",
            },
        }
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
            Route("/", base.home),
            Route("/login", auth.login),
            Route("/oauth2/callback", auth.auth_callback),
            Route("/logout", auth.logout),
            Route("/profile", base.profile),
            Route("/protected", base.protected),
            Route("/set-language/{lang}", base.set_language, name="set_language"),
            Mount("/projects", name="projects", routes=projects_routes),
            Mount("/survey-missions", name="survey_missions", routes=missions_routes),
            Mount(
                "/survey-related-records",
                name="survey_related_records",
                routes=records_routes,
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
