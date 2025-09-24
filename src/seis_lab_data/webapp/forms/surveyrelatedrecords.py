import logging

import pydantic
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    Form,
    FormField,
    SelectField,
    StringField,
)

from ... import (
    constants,
    schemas,
)
from ...db.queries import get_survey_related_record_by_english_name
from .common import (
    DescriptionForm,
    get_form_field_by_name,
    LinkForm,
    NameForm,
    retrieve_form_field_by_pydantic_loc,
)

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

    async def check_if_english_name_is_unique_for_survey_mission(
        self, session: AsyncSession, survey_mission_id: schemas.SurveyMissionId
    ):
        if await get_survey_related_record_by_english_name(
            session, survey_mission_id, self.name.en.data
        ):
            self.name.en.errors.append(
                _(
                    "There is already a survey-related record with this english name under the same survey mission"
                )
            )

    def validate_with_schema(self):
        # note: we build the schema manually and make sure to not use
        # sub-schemas, but rather provide data with lists and dicts. This is
        # in order to ensure pydantic validates the full set of data at once and
        # includes full error locations - otherwise it would be harder to match
        # pydantic validation errors with wtforms field errors
        try:
            schemas.SurveyRelatedRecordCreate(
                # these are not part of the form, but we must provide something
                id=None,
                owner=None,
                survey_mission_id=None,
                name={
                    **get_form_field_by_name(self, "name").data,
                },
                description={
                    **get_form_field_by_name(self, "description").data,
                },
                dataset_category_id=self.dataset_category_id.data,
                domain_type_id=self.domain_type_id.data,
                workflow_stage_id=self.workflow_stage_id.data,
                relative_path=self.relative_path.data,
                links=[
                    {
                        "url": li.url.data,
                        "media_type": li.media_type.data,
                        "relation": li.relation.data,
                        "link_description": {
                            **li.link_description.data,
                        },
                    }
                    for li in self.links.entries
                ],
                assets=[
                    {
                        # not part of the form, but we must provide something
                        "id": None,
                        "name": {**ass.asset_name.data},
                        "description": {**ass.asset_description.data},
                        "relative_path": ass.relative_path.data,
                        "links": [
                            {
                                "url": assli.url.data,
                                "media_type": assli.media_type.data,
                                "relation": assli.relation.data,
                                "link_description": {**assli.link_description.data},
                            }
                            for assli in ass.asset_links.entries
                        ],
                    }
                    for ass in self.assets.entries
                ],
            )
        except pydantic.ValidationError as exc:
            logger.error(f"pydantic errors {exc.errors()=}")
            for error in exc.errors():
                if "id" in error["loc"]:
                    # we don't care about validating errors related to missing id fields,
                    # as the forms never have them
                    continue
                loc = error["loc"]
                logger.debug(f"Analyzing error {loc=} {error['msg']=}...")
                form_field = retrieve_form_field_by_pydantic_loc(self, loc)
                logger.debug(f"{form_field=}")
                if form_field is not None:
                    try:
                        form_field.errors.append(error["msg"])
                    except AttributeError:
                        form_field.errors[None] = error["msg"]
                    logger.debug(f"Form field errors {form_field.errors=}")
                else:
                    logger.debug(f"Unable to find form field for {loc=}")

    def has_validation_errors(self) -> bool:
        # For some unknown reason, wtforms does not report validation errors for
        # listfields together with the other validation errors. This may
        # have something to with the fact that we are setting the 'errors' property
        # of fields manually when performing in the `validate_with_schema()` method.
        # Anyway, we need to employ the below workaround in order
        # to verify if the form contains any erors.
        all_form_validation_errors = {**self.errors}
        logger.debug(f"{all_form_validation_errors=}")
        for link in self.links.entries:
            all_form_validation_errors.update(**link.errors)
        for asset in self.assets.entries:
            all_form_validation_errors.update(**asset.errors)
        logger.debug(f"{all_form_validation_errors=}")
        return not bool(all_form_validation_errors)
