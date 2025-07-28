import contextlib
from typing import (
    AsyncIterator,
    TypedDict,
)

import jinja2
from starlette.applications import Starlette
from starlette_babel.contrib.jinja import configure_jinja_env
from starlette.middleware import Middleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette_babel import (
    get_translator,
    LocaleMiddleware,
)

from .. import config

from .routes import routes


class State(TypedDict):
    settings: config.SeisLabDataSettings
    templates: Jinja2Templates


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    settings = config.get_settings()
    shared_translator = get_translator()
    shared_translator.load_from_directory(settings.translations_dir)
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(settings.templates_dir), autoescape=True
    )
    configure_jinja_env(jinja_env)
    templates = Jinja2Templates(env=jinja_env)
    yield State(
        settings=settings,
        templates=templates,
    )


def create_app_from_settings(settings: config.SeisLabDataSettings) -> Starlette:
    app = Starlette(
        debug=settings.debug,
        routes=routes,
        lifespan=lifespan,
        middleware=[
            Middleware(
                LocaleMiddleware,
                locales=settings.locales,
                default_locale=settings.locales[0],
            )
        ],
    )
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    return app


def create_app() -> Starlette:
    settings = config.get_settings()
    return create_app_from_settings(settings)
