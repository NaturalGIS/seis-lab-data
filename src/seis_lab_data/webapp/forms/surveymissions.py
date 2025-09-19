import logging

from sqlmodel.ext.asyncio.session import AsyncSession
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    FormField,
    StringField,
)

from ... import (
    constants,
    schemas,
)
from ...db.queries import get_survey_mission_by_english_name
from .common import NameForm, DescriptionForm, LinkForm

logger = logging.getLogger(__name__)


class SurveyMissionCreateForm(StarletteForm):
    # This form performs only a very light validation of user input
    # There is a more thorough validation phase when checking if the
    # survey mission can be made public - the idea is to let the creation process
    # succeed (as much as possible) and give the user a chance to fix errors
    # later
    # A notable exception is we do want to validate the max length of string-based
    # inputs
    name = FormField(NameForm)
    description = FormField(DescriptionForm)
    relative_path = StringField(
        _("Relative path"),
        description=_(
            "Path for the survey mission in the archive file system, "
            "relative to its parent project root path"
        ),
    )
    links = FieldList(
        FormField(LinkForm),
        label=_("Links"),
        min_entries=0,
        max_entries=constants.SURVEY_MISSION_MAX_LINKS,
    )

    async def check_if_english_name_is_unique_for_project(
        self, session: AsyncSession, project_id: schemas.ProjectId
    ):
        if await get_survey_mission_by_english_name(
            session, project_id, self.name.en.data
        ):
            self.name.en.errors.append(
                _(
                    "There is already a survey mission with this english name under the same project"
                )
            )
