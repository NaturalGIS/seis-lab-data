import logging
import typing

import pydantic
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    Field,
    FieldList,
    Form,
    FormField,
    StringField,
    TextAreaField,
    validators,
)

from .. import constants

logger = logging.getLogger(__name__)


def validate_form_with_model(
    form_instance: StarletteForm,
    model_class: typing.Type[pydantic.BaseModel],
    extra_model_data: dict | None = None,
) -> StarletteForm:
    try:
        model_class(**form_instance.data, **(extra_model_data or {}))
    except pydantic.ValidationError as exc:
        logger.error(f"pydantic errors {exc.errors()=}")
        for error in exc.errors():
            loc = error["loc"]
            logger.debug(f"Analyzing error {loc=}...")
            form_field = _retrieve_form_field_by_pydantic_loc(form_instance, loc)
            logger.debug(f"Form field {form_field=}")
            if form_field is not None:
                try:
                    form_field.errors.append(error["msg"])
                except AttributeError:
                    form_field.errors[None] = error["msg"]
            else:
                logger.debug(f"Unable to find form field for {loc=}")
    return form_instance


def _retrieve_form_field_by_pydantic_loc(
    form_instance: StarletteForm, loc: tuple
) -> Field | None:
    parent = form_instance
    field = None
    for part in loc:
        field = getattr(parent, part, None)
        if field is None:
            break
        parent = field
    return field


class NameForm(Form):
    en = StringField(
        _("English name"),
        description=_("Name of the project in english"),
        validators=[
            # validators.DataRequired(message=_("English name is required")),
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )
    pt = StringField(
        _("Portuguese name"),
        description=_("Name of the project in portuguese"),
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
        description=_("Description of the project in english"),
        validators=[
            validators.Length(
                max=constants.DESCRIPTION_MAX_LENGTH,
            ),
        ],
    )
    pt = TextAreaField(
        _("Portuguese description"),
        description=_("Description of the project in portuguese"),
        validators=[
            validators.Length(
                max=constants.DESCRIPTION_MAX_LENGTH,
            ),
        ],
    )


class LinkForm(Form):
    # url = StringField(_("URL"), validators=[validators.DataRequired()])
    url = StringField(_("URL"))
    media_type = StringField(_("Media type"))
    relation = StringField(_("Relation"))
    description_en = StringField(_("English description"))
    description_pt = StringField(_("Portuguese description"))


class ProjectCreateForm(StarletteForm):
    # This form performs only a very light validation of user input
    # There is a more thorough validation phase when checking if the
    # project can be made public - the idea is to let the creation process
    # succeed (as much as possible) and give the user a chance to fix errors
    # later
    # A notable exception is we do want to validate the max length of string-based
    # inputs
    name = FormField(NameForm)
    description = FormField(DescriptionForm)
    root_path = StringField(
        _("Root path"),
        description=_("Base path for the project in the archive file system"),
    )
    links = FieldList(
        FormField(LinkForm),
        label=_("Links"),
        min_entries=0,
        max_entries=constants.PROJECT_MAX_LINKS,
    )
