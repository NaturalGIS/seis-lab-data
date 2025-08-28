import enum
import datetime as dt
import dataclasses
from functools import partial


class EventType(enum.Enum):
    MARINE_CAMPAIGN_CREATED = "marine_campaign_created"
    DATASET_CATEGORY_CREATED = "dataset_category_created"
    DATASET_CATEGORY_DELETED = "dataset_category_deleted"
    DOMAIN_TYPE_CREATED = "domain_type_created"
    DOMAIN_TYPE_DELETED = "domain_type_deleted"
    WORKFLOW_STAGE_CREATED = "workflow_stage_created"
    WORKFLOW_STAGE_DELETED = "workflow_stage_deleted"

    MARINE_CAMPAIGN_VALIDATED = "marine_campaign_validated"
    MARINE_CAMPAIGN_VALIDATION_PROGRESS = "marine_campaign_validation_progress"


get_utc_now = partial(dt.datetime.now, tz=dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class EventPayload:
    before: dict | None = None
    after: dict | None = None


@dataclasses.dataclass(frozen=True)
class SeisLabDataEvent:
    type_: EventType
    initiator: str
    payload: EventPayload
    timestamp: dt.datetime = dataclasses.field(default=get_utc_now)
