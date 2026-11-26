"""FastAPI app for a readonly STAC API.

NOTE: We do not use any lifespan-related functionality when setting up this
FastAPI application because the way that it gets used at runtime is by being
mounted by our main starlette-based app. Therefore, lifespan is configured
in the starlette app.
"""

from fastapi import (
    FastAPI,
    Request,
)
from starlette.responses import JSONResponse

from ... import (
    config,
    errors,
)
from .routers import router


def create_api_app() -> FastAPI:
    return create_api_app_from_settings(config.get_settings())


def create_api_app_from_settings(settings: config.SeisLabDataSettings) -> FastAPI:
    app = FastAPI(
        title="SeisLabData STAC API",
        summary="Read-only STAC API of the SeisLabData marine survey data catalog",
        description=(
            "Read-only [STAC](https://stacspec.org/) API of the published contents of "
            "the SeisLabData catalog. Projects are exposed as catalogs, survey missions "
            "as collections and survey-related records as items, whose assets link to "
            "the download of their data files.\n\n"
            "Listings are paginated with the `page` and `limit` parameters, and "
            "include `next` and `prev` links. See the "
            f"[user guide]({settings.docs_url.rstrip('/')}/user-guide/#stac-api) for "
            "a description of the API and usage examples."
        ),
        openapi_tags=[
            {
                "name": "Core",
                "description": "Landing page and conformance classes of the API.",
            },
            {
                "name": "Catalogs",
                "description": "Projects, as catalogs, and their survey missions.",
            },
            {
                "name": "Collections",
                "description": "Survey missions, as collections, and their items.",
            },
            {
                "name": "Item search",
                "description": "Search for items across all collections.",
            },
        ],
        version=settings.version,
        servers=[{"url": f"{settings.public_url}/stac"}],
        root_path_in_servers=False,
    )

    @app.exception_handler(errors.UserNotAllowedError)
    async def _private_resource_as_not_found(
        request: Request, exc: errors.UserNotAllowedError
    ) -> JSONResponse:
        # a private resource must be indistinguishable from a nonexistent one
        # to an anonymous STAC client
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    app.include_router(router)
    return app
