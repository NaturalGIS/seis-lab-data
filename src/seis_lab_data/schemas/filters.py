import dataclasses
import datetime as dt


@dataclasses.dataclass
class TemporalExtentFilterValue:
    begin: dt.date | None
    end: dt.date | None
