import logging
from wtforms.fields import DateField

logger = logging.getLogger(__name__)


class OptionalDateField(DateField):
    def process_formdata(self, valuelist):
        logger.debug(f"{valuelist=}")
        if len(valuelist) == 1 and valuelist[0] == "":
            self.data = None
            return
        else:
            return super().process_formdata(valuelist)
