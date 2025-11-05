import enum
import datetime as dt
import dataclasses
from functools import partial


class EventType(enum.Enum):
    ASSET_CREATED = "asset_created"
    ASSET_DELETED = "asset_deleted"
    ASSET_UPDATED = "asset_updated"
    DATASET_CATEGORY_CREATED = "dataset_category_created"
    DATASET_CATEGORY_DELETED = "dataset_category_deleted"
    DOMAIN_TYPE_CREATED = "domain_type_created"
    DOMAIN_TYPE_DELETED = "domain_type_deleted"
    PROJECT_CREATED = "project_created"
    PROJECT_DELETED = "project_deleted"
    PROJECT_UPDATED = "project_updated"
    PROJECT_VALIDATED = "project_validated"
    PROJECT_VALIDATION_PROGRESS = "project_validation_progress"
    PROJECT_STATUS_CHANGED = "project_status_changed"
    SURVEY_MISSION_CREATED = "survey_mission_created"
    SURVEY_MISSION_DELETED = "survey_mission_deleted"
    SURVEY_MISSION_UPDATED = "survey_mission_updated"
    SURVEY_MISSION_VALIDATED = "survey_mission_validated"
    SURVEY_MISSION_VALIDATION_PROGRESS = "survey_mission_validation_progress"
    SURVEY_RELATED_RECORD_CREATED = "survey_related_record_created"
    SURVEY_RELATED_RECORD_DELETED = "survey_related_record_deleted"
    SURVEY_RELATED_RECORD_UPDATED = "survey_related_record_updated"
    SURVEY_RELATED_RECORD_VALIDATED = "survey_related_record_validated"
    SURVEY_RELATED_RECORD_VALIDATION_PROGRESS = (
        "survey_related_record_validation_progress"
    )
    WORKFLOW_STAGE_CREATED = "workflow_stage_created"
    WORKFLOW_STAGE_DELETED = "workflow_stage_deleted"


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
    timestamp: dt.datetime = dataclasses.field(default_factory=get_utc_now)
