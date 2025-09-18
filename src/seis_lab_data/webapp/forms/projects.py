import logging

from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    FormField,
    StringField,
)

from .common import (
    DescriptionForm,
    LinkForm,
    NameForm,
)
from ... import constants

logger = logging.getLogger(__name__)


class ProjectCreateForm(StarletteForm):
    # This form performs only a very light validation of user input
    # There is a more thorough validation phase when checking if the
    # project can be made public - the idea is to let the creation process
    # succeed (as much as possible) and give the user a chance to fix errors
    # later
    # A notable exception is we do want to validate the max length of string-based
    # inputs
    name = FormField(NameForm)
    slug = StringField(
        _("Slug"),
        description=_(
            f"Short label for the project, to be used in URLs and file paths. "
            f"Allowed characters are letters, numbers, and hyphen. "
            f"Additionally, it cannot exceed {constants.NAME_MAX_LENGTH} "
            f"characters"
        ),
    )
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
