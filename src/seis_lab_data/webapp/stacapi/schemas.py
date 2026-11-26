import pydantic
import stac_pydantic.api as stac_api


# `stac_pydantic.api.Search` only models `limit`, while the listings of this API are
# paginated with `page` and `limit`, so this adds `page`. The docstring is the
# description of the schema in the OpenAPI document
class Search(stac_api.Search):
    """Criteria of an item search, which must all be met by the returned items."""

    page: int | None = pydantic.Field(
        None, description="Number of the page of results to return, starting at 1."
    )
