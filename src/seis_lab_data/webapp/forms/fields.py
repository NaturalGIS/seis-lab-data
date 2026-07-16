import json
import logging
from wtforms.fields import (
    DateField,
    Field,
)
from wtforms.widgets import HiddenInput
from wtforms.validators import ValidationError

logger = logging.getLogger(__name__)


class JsonEditorField(Field):
    widget = HiddenInput()

    default_structure: dict

    def __init__(
        self,
        label: str | None = None,
        validators=None,
        default_structure=None,
        **kwargs,
    ):
        super().__init__(label, validators, **kwargs)
        self.default_structure = default_structure or {}

    def _value(self):
        if self.data is not None:
            return json.dumps(self.data)
        return json.dumps(self.default_structure)

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = json.loads(valuelist[0])
            except (ValueError, TypeError) as err:
                raise ValidationError("Invalid JSON submitted") from err


class OptionalDateField(DateField):
    def process_formdata(self, valuelist):
        if len(valuelist) == 1 and valuelist[0] == "":
            self.data = None
            return
        else:
            return super().process_formdata(valuelist)
