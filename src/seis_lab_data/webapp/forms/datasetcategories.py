import json
import logging

import pydantic
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from starlette_babel import gettext_lazy as _
from starlette_wtf import StarletteForm
from wtforms import HiddenField

from ...db.queries.datasetcategories import get_dataset_category_by_english_name
from ...schemas import (
    datasetcategories as category_schemas,
    identifiers,
)
from .common import incorporate_schema_validation_errors_into_form
from .fields import JsonEditorField

logger = logging.getLogger(__name__)


class _BaseForm(StarletteForm):
    """Base form for dataset categories."""

    request_id = HiddenField()
    name = JsonEditorField(
        label=_("name"),
        default_structure={"en": "", "pt": ""},
    )

    def _parse_name(self) -> dict | None:
        value: dict[str, str] = self.name.data
        if not value:
            return None
        try:
            if value.get("en", "") == "":
                self.name.errors.append("Must provide at least english name")
                return None
            return value
        except json.JSONDecodeError:
            self.name.errors.append(_("Invalid JSON"))
            return None
        except pydantic.ValidationError as exc:
            self.name.errors.append(
                "; ".join(
                    f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                )
            )
            return None

    async def check_if_english_name_is_unique(
        self,
        session: AsyncSession,
        disregard_id: identifiers.DatasetCategoryId | None = None,
    ):
        """Check if current english name is already used by another dataset category.

        The `disregard_id` argument can be used when checking uniqueness of
        the english name in the context of updating an already existing dataset
        category, in which case the category itself should be disregarded, as
        it is not a conflict for a category to have the same english name
        as itself.
        """
        error_message = _("There is already a dataset category with this english name")
        if (parsed_name := self._parse_name()) is None:
            return
        if candidate := await get_dataset_category_by_english_name(
            session, parsed_name["en"]
        ):
            if disregard_id:
                if identifiers.DatasetCategoryId(candidate.id) != disregard_id:
                    self.name.errors.append(error_message)
            else:
                self.name.errors.append(error_message)

    def has_validation_errors(self) -> bool:
        all_form_validation_errors = {**self.errors}
        logger.debug(f"{all_form_validation_errors=}")
        return bool(all_form_validation_errors)

    def validate_with_schema(self) -> None:
        raise NotImplementedError()

    @classmethod
    async def get_validated_form_instance(
        cls, request: Request, disregard_id: identifiers.DatasetCategoryId | None = None
    ):
        """Performs full validation of an asset_discovery_configuration-related form.

        This performs multiple validations:

        - validate the form with WTForms' validation logic
        - validate the form data with our custom pydantic model
        - validate that the English name is unique across projects

        The already validated form instance is returned.
        """

        form_instance = await cls.from_formdata(request)
        # first validate the form with WTForms' validation logic
        # then validate the form data with our custom pydantic model
        await form_instance.validate_on_submit()
        form_instance.validate_with_schema()
        session_maker = request.state.settings.get_db_session_maker()
        async with session_maker() as session:
            await form_instance.check_if_english_name_is_unique(
                session, disregard_id=disregard_id
            )
        return form_instance


class DatasetCategoryCreateForm(_BaseForm):
    def validate_with_schema(self):
        try:
            category_schemas.DatasetCategoryCreate(
                # id is not part of the form, but we must provide something
                id=None,
                name=self.name.data,
            )
        except pydantic.ValidationError as exc:
            incorporate_schema_validation_errors_into_form(exc.errors(), self)


class DatasetCategoryUpdateForm(_BaseForm):
    def validate_with_schema(self):
        try:
            category_schemas.DatasetCategoryUpdate(
                name=self.name.data,
            )
        except pydantic.ValidationError as exc:
            incorporate_schema_validation_errors_into_form(exc.errors(), self)
