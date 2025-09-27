import logging

import pydantic
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
from ...db.queries import get_project_by_english_name
from .common import (
    DescriptionForm,
    get_form_field_by_name,
    LinkForm,
    NameForm,
    retrieve_form_field_by_pydantic_loc,
)

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

    def validate_with_schema(self):
        # note: we build the schema manually and make sure to not use
        # sub-schemas, but rather provide data with lists and dicts. This is
        # in order to ensure pydantic validates the full set of data at once and
        # includes full error locations - otherwise it would be harder to match
        # pydantic validation errors with wtforms field errors
        try:
            schemas.ProjectCreate(
                # these are not part of the form, but we must provide something
                id=None,
                owner=None,
                name={
                    **get_form_field_by_name(self, "name").data,
                },
                description={
                    **get_form_field_by_name(self, "description").data,
                },
                root_path=self.root_path.data,
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
        # to verify if the form contains any errors.
        all_form_validation_errors = {**self.errors}
        for link in self.links.entries:
            all_form_validation_errors.update(**link.errors)
        logger.debug(f"{all_form_validation_errors=}")
        return bool(all_form_validation_errors)


class ProjectUpdateForm(ProjectCreateForm):
    def validate_with_schema(self):
        # note: we build the schema manually and make sure to not use
        # sub-schemas, but rather provide data with lists and dicts. This is
        # in order to ensure pydantic validates the full set of data at once and
        # includes full error locations - otherwise it would be harder to match
        # pydantic validation errors with wtforms field errors
        try:
            schemas.ProjectUpdate(
                owner=None,
                name={
                    **get_form_field_by_name(self, "name").data,
                },
                description={
                    **get_form_field_by_name(self, "description").data,
                },
                root_path=self.root_path.data,
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
