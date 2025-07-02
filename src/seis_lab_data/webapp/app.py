import contextlib
from typing import (
    AsyncIterator,
    TypedDict,
)

from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .. import config

from .routes import routes


class State(TypedDict):
    settings: config.SeisLabDataSettings
    templates: Jinja2Templates


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    settings = config.get_settings()
    templates = Jinja2Templates(settings.templates_dir)
    yield State(
        settings=settings,
        templates=templates,
    )


def create_app_from_settings(settings: config.SeisLabDataSettings) -> Starlette:
    app = Starlette(
        debug=settings.debug,
        routes=routes,
        lifespan=lifespan,
    )
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    return app


def create_app() -> Starlette:
    settings = config.get_settings()
    return create_app_from_settings(settings)
