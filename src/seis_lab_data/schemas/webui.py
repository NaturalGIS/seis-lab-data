import pydantic
from starlette_babel import LazyString
from starlette.datastructures import URL


class BreadcrumbItem(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    name: LazyString | str
    url: URL | str | None = None
