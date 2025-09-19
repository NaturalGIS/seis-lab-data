import logging

from sqlmodel.ext.asyncio.session import AsyncSession
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
from ...db.queries import get_project_by_english_name

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

    async def check_if_english_name_is_unique(self, session: AsyncSession):
        if await get_project_by_english_name(session, self.name.en.data):
            self.name.en.errors.append(
                _("There is already a project with this english name")
            )
