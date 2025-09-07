from starlette_wtf import StarletteForm
from wtforms import (
    StringField,
    TextAreaField,
    validators,
)

from .. import constants


class ProjectCreateForm(StarletteForm):
    name = StringField(
        "name",
        description="Name of the project",
        validators=[
            validators.Length(
                min=constants.NAME_MIN_LENGTH, max=constants.NAME_MAX_LENGTH
            ),
        ],
    )
    description = TextAreaField(
        "description",
        description="A short description of the project",
        validators=[
            validators.Length(max=constants.DESCRIPTION_MAX_LENGTH),
        ],
    )
    root_path = StringField(
        "root path",
        description="Base path for the project in the archive file system",
    )
