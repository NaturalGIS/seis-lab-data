from decimal import Decimal
import logging
import typing

import pydantic
from starlette.requests import Request
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    DecimalField,
    Field,
    Form,
    StringField,
    validators,
    TextAreaField,
    URLField,
    FormField,
)

from seis_lab_data import constants

logger = logging.getLogger(__name__)


class FormProtocol(typing.Protocol):
    schema: pydantic.BaseModel

    @classmethod
    async def from_formdata(cls, request: Request) -> "cls":  # noqa
        raise NotImplementedError()

    async def validate_on_submit(self) -> Form:
        raise NotImplementedError()

    def validate_with_schema(self) -> None:
        raise NotImplementedError()

    def has_validation_errors(self) -> bool:
        raise NotImplementedError()


def get_form_field_by_name(form: Form | FormField, name: str) -> Field | None:
    """Retrieve a field by its name"""
    for field in form:
        if field.short_name == name:
            return field
    else:
        return None


def incorporate_schema_validation_errors_into_form(
    schema_validation_errors: list[dict], form_: Form
) -> None:
    """Incorporate pydantic validation errors into a WTForms form instance.

    This is useful when a pydantic schema is used to validate data
    that was originally collected with a WTForms form, and we want
    to show the validation errors in the form itself.
    """
    for error in schema_validation_errors:
        if "id" in error["loc"]:
            # we don't care about validating errors related to missing id fields,
            # as the forms never have them
            continue
        loc = error["loc"]
        logger.debug(f"Analyzing error {loc=} {error['msg']=}...")
        form_field = retrieve_form_field_by_pydantic_loc(form_, loc)
        logger.debug(f"{form_field=}")
        if form_field is not None:
            try:
                form_field.errors.append(error["msg"])
            except AttributeError:
                form_field.errors[None] = error["msg"]
            logger.debug(f"Form field errors {form_field.errors=}")
        else:
            logger.debug(f"Unable to find form field for {loc=}")


def retrieve_form_field_by_pydantic_loc(
    form_instance: StarletteForm, loc: tuple
) -> Field | None:
    parent = form_instance
    field = None
    for part in loc:
        if isinstance(part, int):
            field = parent.entries[part]
        else:
            for f in parent:
                if f.short_name == part:
                    field = f
                    break
            else:
                field = None
        if field is None:
            break
        parent = field
    return field


class NameForm(Form):
    en = StringField(
        _("English name"),
        description=_("Name of the item in english"),
        validators=[
            # validators.DataRequired(message=_("English name is required")),
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )
    pt = StringField(
        _("Portuguese name"),
        description=_("Name of the item in portuguese"),
        validators=[
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make 'en' field required
        self.en.flags.backend_required = True


class DescriptionForm(Form):
    en = TextAreaField(
        _("English description"),
        description=_("Short english description about this item"),
        validators=[
            validators.Length(
                max=constants.DESCRIPTION_MAX_LENGTH,
            ),
        ],
    )
    pt = TextAreaField(
        _("Portuguese description"),
        description=_("Short portuguese description about this item"),
        validators=[
            validators.Length(
                max=constants.DESCRIPTION_MAX_LENGTH,
            ),
        ],
    )


class LinkForm(Form):
    url = URLField(_("URL"))
    media_type = StringField(_("Media type"))
    relation = StringField(_("Relation"))
    link_description = FormField(DescriptionForm)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url.flags.backend_required = True


class BoundingBoxForm(Form):
    min_lon = DecimalField(
        "min_lon", default=Decimal(0), places=5, render_kw={"min": -180, "max": 180}
    )
    max_lon = DecimalField(
        "max_lon", default=Decimal(0), places=5, render_kw={"min": -180, "max": 180}
    )
    min_lat = DecimalField(
        "min_lat", default=Decimal(0), places=5, render_kw={"min": -90, "max": 90}
    )
    max_lat = DecimalField(
        "max_lat", default=Decimal(0), places=5, render_kw={"min": -90, "max": 90}
    )
