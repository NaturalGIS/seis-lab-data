import logging
import uuid

import pydantic
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    FieldList,
    Form,
    FormField,
    HiddenField,
    SelectField,
    StringField,
)

from ... import (
    constants,
    schemas,
)
from ...db import (
    models,
    queries,
)
from .common import (
    DescriptionForm,
    get_form_field_by_name,
    incorporate_schema_validation_errors_into_form,
    LinkForm,
    NameForm,
)

logger = logging.getLogger(__name__)


def _generate_new_asset_id() -> str:
    return str(uuid.uuid4())


class AssetCreateForm(Form):
    asset_id = HiddenField("asset_id", default=_generate_new_asset_id)
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


class _SurveyRelatedRecordForm(StarletteForm):
    """Base form for survey-related records.

    This form performs only a very light validation of user input.
    There is a more thorough validation phase when checking if the
    record can be made public - the idea is to let the creation process
    succeed (as much as possible) and give the user a chance to fix errors
    later.
    A notable exception is we do want to validate the max length of string-based
    inputs and their uniqueness.
    """

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
        self,
        session: AsyncSession,
        survey_mission_id: schemas.SurveyMissionId,
        disregard_id: schemas.SurveyRelatedRecordId | None = None,
    ):
        """Check if the current english name is already used by another record under the same survey mission.

        The `disregard_id` argument can be used when checking uniqueness of the english name in the
        context of updating an already existing record, in which case the record itself should be
        disregarded, as it is not a conflict for a record to have the same english name as itself.
        """
        error_message = _(
            "There is already a survey-related record with this english name under the same survey mission"
        )
        if candidate := await queries.get_survey_related_record_by_english_name(
            session, survey_mission_id, self.name.en.data
        ):
            if disregard_id:
                if schemas.SurveyRelatedRecordId(candidate.id) != disregard_id:
                    self.name.en.errors.append(error_message)
            else:
                self.name.en.errors.append(error_message)

    def has_validation_errors(self) -> bool:
        # For some unknown reason, wtforms does not report validation errors for
        # listfields together with the other validation errors. This may
        # have something to do with the fact that we are setting the 'errors' property
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

    def validate_with_schema(self) -> None:
        raise NotImplementedError()

    @classmethod
    async def from_request(cls, request):
        """Creates a form instance from the request.

        This method's main reason for existing is to ensure select fields are
        populated dynamically, with choices from the database.
        """
        form_instance = await cls.from_formdata(request)
        current_language = request.state.language
        async with request.state.session_maker() as session:
            form_instance.dataset_category_id.choices = [
                (dc.id, dc.name.get(current_language, dc.name["en"]))
                for dc in await queries.collect_all_dataset_categories(
                    session,
                    order_by_clause=models.DatasetCategory.name[
                        current_language
                    ].astext,
                )
            ]
            form_instance.domain_type_id.choices = [
                (dt.id, dt.name.get(current_language, dt.name["en"]))
                for dt in await queries.collect_all_domain_types(
                    session,
                    order_by_clause=models.DomainType.name[current_language].astext,
                )
            ]
            form_instance.workflow_stage_id.choices = [
                (ws.id, ws.name.get(current_language, ws.name["en"]))
                for ws in await queries.collect_all_workflow_stages(
                    session,
                    order_by_clause=models.WorkflowStage.name[current_language].astext,
                )
            ]
        return form_instance

    @classmethod
    async def get_validated_form_instance(
        cls,
        request: Request,
        survey_mission_id: schemas.SurveyMissionId,
        disregard_id: schemas.SurveyRelatedRecordId | None = None,
    ):
        """Performs full validation of a mission-related record form.

        This performs multiple validations:

        - validate the form with WTForms' validation logic
        - validate the form data with our custom pydantic model
        - validate that the English name is unique across records of the same
        mission

        The already validated form instance is returned.
        """

        form_instance = await cls.from_request(request)
        await form_instance.validate_on_submit()
        form_instance.validate_with_schema()
        session_maker = request.state.session_maker
        async with session_maker() as session:
            await form_instance.check_if_english_name_is_unique_for_survey_mission(
                session, survey_mission_id=survey_mission_id, disregard_id=disregard_id
            )
        return form_instance


class SurveyRelatedRecordCreateForm(_SurveyRelatedRecordForm):
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
                name={**get_form_field_by_name(self, "name").data},
                description={**get_form_field_by_name(self, "description").data},
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
            incorporate_schema_validation_errors_into_form(exc.errors(), self)


class SurveyRelatedRecordUpdateForm(_SurveyRelatedRecordForm):
    def validate_with_schema(self):
        # note: we build the schema manually and make sure to not use
        # sub-schemas, but rather provide data with lists and dicts. This is
        # in order to ensure pydantic validates the full set of data at once and
        # includes full error locations - otherwise it would be harder to match
        # pydantic validation errors with wtforms field errors
        try:
            schemas.SurveyRelatedRecordUpdate(
                # these are not part of the form, but we must provide something
                owner=None,
                survey_mission_id=None,
                name={**get_form_field_by_name(self, "name").data},
                description={**get_form_field_by_name(self, "description").data},
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
            incorporate_schema_validation_errors_into_form(exc.errors(), self)
