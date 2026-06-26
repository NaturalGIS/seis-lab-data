import logging

import pydantic
from starlette.requests import Request
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import (
    HiddenField,
    SelectField,
    StringField,
    validators,
)

from ... import constants
from ...db import models
from ...db.queries import surveyrelatedrecords as record_queries
from ...schemas import discovery as discovery_schemas
from .common import incorporate_schema_validation_errors_into_form

logger = logging.getLogger(__name__)


class _AssetDiscoveryConfigurationForm(StarletteForm):
    """Base form for asset_discovery configurations."""

    request_id = HiddenField()
    name = StringField(
        _("Name"),
        description=_("Name for identifying this configuration"),
        validators=[
            validators.Length(
                max=constants.NAME_MAX_LENGTH,
            ),
        ],
    )
    relative_path_regexp = StringField(
        _("Relative path regular expression"),
        description=_(
            "A regular expression that is used to find the respective file on the filesystem"
        ),
    )
    dataset_category_id = SelectField(_("Dataset category"))
    workflow_stage_id = SelectField(_("Workflow stage"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make 'name' field required
        self.name.flags.backend_required = True

    def has_validation_errors(self) -> bool:
        all_form_validation_errors = {**self.errors}
        logger.debug(f"{all_form_validation_errors=}")
        return bool(all_form_validation_errors)

    def validate_with_schema(self) -> None:
        raise NotImplementedError()

    @classmethod
    async def from_request(cls, request, data: dict | None = None):
        """Creates a form instance from the request.

        This method's main reason for existing is to ensure select fields are
        populated dynamically, with choices from the database.
        """
        if data:
            form_instance = cls(request, data=data)
        else:
            form_instance = await cls.from_formdata(request)
        current_language = request.state.language
        async with request.state.settings.get_db_session_maker()() as session:
            form_instance.dataset_category_id.choices = [
                (dc.id, dc.name.get(current_language, dc.name["en"]))
                for dc in await record_queries.collect_all_dataset_categories(
                    session,
                    order_by_clause=models.DatasetCategory.name[
                        current_language
                    ].astext,
                )
            ]
            form_instance.workflow_stage_id.choices = [
                (ws.id, ws.name.get(current_language, ws.name["en"]))
                for ws in await record_queries.collect_all_workflow_stages(
                    session,
                    order_by_clause=models.WorkflowStage.name[current_language].astext,
                )
            ]
        return form_instance

    @classmethod
    async def get_validated_form_instance(cls, request: Request):
        """Performs full validation of an asset_discovery_configuration-related form.

        This performs multiple validations:

        - validate the form with WTForms' validation logic
        - validate the form data with our custom pydantic model
        - validate that the English name is unique across projects

        The already validated form instance is returned.
        """

        form_instance = await cls.from_request(request)
        # first validate the form with WTForms' validation logic
        # then validate the form data with our custom pydantic model
        await form_instance.validate_on_submit()
        form_instance.validate_with_schema()
        return form_instance


class AssetDiscoveryConfigurationCreateForm(_AssetDiscoveryConfigurationForm):
    def validate_with_schema(self):
        try:
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                # id is not part of the form, but we must provide something
                id=None,
                name=self.name.data,
                relative_path_regexp=self.relative_path_regexp.data,
                dataset_category_id=self.dataset_category_id.data,
                workflow_stage_id=self.workflow_stage_id.data,
            )
        except pydantic.ValidationError as exc:
            incorporate_schema_validation_errors_into_form(exc.errors(), self)


class AssetDiscoveryConfigurationUpdateForm(_AssetDiscoveryConfigurationForm):
    def validate_with_schema(self):
        try:
            discovery_schemas.AssetDiscoveryConfigurationUpdate(
                name=self.name.data,
                relative_path_regexp=self.relative_path_regexp.data,
                dataset_category_id=self.dataset_category_id.data,
                workflow_stage_id=self.workflow_stage_id.data,
            )
        except pydantic.ValidationError as exc:
            incorporate_schema_validation_errors_into_form(exc.errors(), self)
