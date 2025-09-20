import logging

from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    Form,
    FormField,
    SelectField,
    StringField,
)

from ... import constants
from .common import NameForm, DescriptionForm, LinkForm

logger = logging.getLogger(__name__)


class AssetCreateForm(Form):
    asset_name = FormField(NameForm, name="name")
    asset_description = FormField(DescriptionForm, name="description")
    relative_path = StringField(
        _("Relative path"),
        description=_(
            "Path for the asset in the archive file system, "
            "relative to its parent survey-related record root path"
        ),
    )
    asset_links = FieldList(
        FormField(LinkForm),
        name="links",
        label=_("Links"),
        min_entries=0,
        max_entries=constants.ASSET_MAX_LINKS,
    )


class SurveyRelatedRecordCreateForm(StarletteForm):
    # This form performs only a very light validation of user input
    # There is a more thorough validation phase when checking if the
    # survey mission can be made public - the idea is to let the creation process
    # succeed (as much as possible) and give the user a chance to fix errors
    # later
    # A notable exception is we do want to validate the max length of string-based
    # inputs
    name = FormField(NameForm)
    description = FormField(DescriptionForm)
    dataset_category_id = SelectField(_("Dataset category"))
    domain_type_id = SelectField(_("Domain type"))
    workflow_stage_id = SelectField(_("Workflow stage"))
    relative_path = StringField(
        _("Relative path"),
        description=_(
            "Path for the survey-related record in the archive file system, "
            "relative to its parent survey mission root path"
        ),
    )
    links = FieldList(
        FormField(LinkForm),
        label=_("Links"),
        min_entries=0,
        max_entries=constants.SURVEY_MISSION_MAX_LINKS,
    )
    assets = FieldList(
        FormField(AssetCreateForm),
        label=_("Assets"),
        min_entries=1,
        max_entries=constants.SURVEY_RELATED_RECORD_MAX_ASSETS,
    )
