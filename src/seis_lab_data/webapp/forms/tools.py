import logging
import typing

import pydantic
from starlette_wtf import StarletteForm
from wtforms import Field

logger = logging.getLogger(__name__)


def validate_form_with_model(
    form_instance: StarletteForm,
    model_class: typing.Type[pydantic.BaseModel],
    **extra_model_data,
) -> StarletteForm:
    try:
        model_class(**form_instance.data, **(extra_model_data or {}))
    except pydantic.ValidationError as exc:
        logger.error(f"pydantic errors {exc.errors()=}")
        for error in exc.errors():
            loc = error["loc"]
            logger.debug(f"Analyzing error {loc=} {error['msg']=}...")
            form_field = _retrieve_form_field_by_pydantic_loc(form_instance, loc)
            logger.debug(f"Form field {form_field=}")
            if form_field is not None:
                try:
                    form_field.errors.append(error["msg"])
                except AttributeError:
                    form_field.errors[None] = error["msg"]
                logger.debug(f"Form field errors {form_field.errors=}")
            else:
                logger.debug(f"Unable to find form field for {loc=}")
    return form_instance


def _retrieve_form_field_by_pydantic_loc(
    form_instance: StarletteForm, loc: tuple
) -> Field | None:
    parent = form_instance
    field = None
    for part in loc:
        if isinstance(part, int):
            field = parent.entries[part]
        else:
            field = getattr(parent, part, None)
        if field is None:
            break
        parent = field
    return field
