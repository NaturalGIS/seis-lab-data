import logging

from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    Form,
    FormField,
    StringField,
    TextAreaField,
    URLField,
    validators,
)

from ... import constants

logger = logging.getLogger(__name__)


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
