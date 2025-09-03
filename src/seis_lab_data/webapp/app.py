import contextlib
from collections.abc import Callable
from typing import (
    AsyncIterator,
    TypedDict,
)

import jinja2
from authlib.integrations.starlette_client import OAuth
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.applications import Starlette
from starlette_babel.contrib.jinja import configure_jinja_env
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette_babel import (
    get_translator,
    LocaleMiddleware,
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

from .routes import routes
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
    engine = get_engine(settings)
    yield State(
        settings=settings,
        templates=templates,
        auth_config=auth_config,
        oauth_manager=get_oauth_manager(auth_config),
        session_maker=get_session_maker(engine),
        event_emitter=events.get_event_emitter(settings),
    )
    await engine.dispose()


def create_app_from_settings(settings: config.SeisLabDataSettings) -> Starlette:
    setup_broker(settings)
    app = Starlette(
        debug=settings.debug,
        routes=routes,
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
        ],
    )
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    return app


def create_app() -> Starlette:
    settings = config.get_settings()
    return create_app_from_settings(settings)
