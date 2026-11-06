import logging
from wtforms.fields import (
    DateField,
    IntegerField,
)

from .. import epsgcodes

logger = logging.getLogger(__name__)


class OptionalDateField(DateField):
    def process_formdata(self, valuelist):
        if len(valuelist) == 1 and valuelist[0] == "":
            self.data = None
            return
        else:
            return super().process_formdata(valuelist)


class EpsgCodeField(IntegerField):
    # the box shows "code - name" while only its leading number is stored
    def process_formdata(self, valuelist):
        if not valuelist:
            return super().process_formdata(valuelist)
        try:
            epsg_code = epsgcodes.extract_epsg_code(valuelist[0])
        except ValueError:
            # no leading number, let IntegerField report its usual error
            return super().process_formdata(valuelist)
        return super().process_formdata([str(epsg_code)])

    def _value(self):
        candidate = self.raw_data[0] if self.raw_data else self.data
        if candidate is None or candidate == "":
            return ""
        try:
            crs_name = epsgcodes.get_epsg_crs_name(str(candidate))
        except ValueError:
            # keep what was typed so the user can fix it
            return str(candidate)
        return f"{epsgcodes.extract_epsg_code(str(candidate))} - {crs_name}"
