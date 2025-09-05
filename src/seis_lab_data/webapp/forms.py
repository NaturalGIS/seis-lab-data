from starlette_wtf import StarletteForm
from wtforms import (
    StringField,
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
