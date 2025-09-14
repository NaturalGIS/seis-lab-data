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
    # url = StringField(_("URL"), validators=[validators.DataRequired()])
    url = URLField(_("URL"))
    media_type = StringField(_("Media type"))
    relation = StringField(_("Relation"))
    link_description = FormField(DescriptionForm)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url.flags.backend_required = True
