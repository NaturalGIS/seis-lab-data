import logging
import typing

import pydantic
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
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


class CreationFormProtocol(typing.Protocol):
    schema: pydantic.BaseModel

    def validate_with_schema(self) -> None:
        raise NotImplementedError

    def has_validation_errors(self) -> bool:
        raise NotImplementedError


def get_form_field_by_name(form: Form | FormField, name: str) -> Field | None:
    """Retrieve a field by its name"""
    for field in form:
        if field.short_name == name:
            return field
    else:
        return None


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
