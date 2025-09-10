from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    Form,
    FormField,
    StringField,
    TextAreaField,
    validators,
)

from .. import constants


class LinkForm(Form):
    url = StringField(_("URL"), validators=[validators.DataRequired()])
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
    name_en = StringField(
        _("English name"),
        description=_("Name of the project in english"),
        validators=[
            validators.DataRequired(message=_("English name is required")),
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )
    name_pt = StringField(
        _("Portuguese name"),
        description=_("Name of the project in portuguese"),
        validators=[
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )
    description_en = TextAreaField(
        _("English description"),
        description=_("A short description of the project in english"),
        validators=[
            validators.Length(max=constants.DESCRIPTION_MAX_LENGTH),
        ],
    )
    description_pt = TextAreaField(
        _("Portuguese description"),
        description=_("A short description of the project in portuguese"),
        validators=[
            validators.Length(max=constants.DESCRIPTION_MAX_LENGTH),
        ],
    )
    root_path = StringField(
        _("Root path"),
        description=_("Base path for the project in the archive file system"),
    )
    links = FieldList(
        FormField(LinkForm),
        label=_("Links"),
        min_entries=1,
        max_entries=constants.PROJECT_MAX_LINKS,
    )
