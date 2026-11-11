import enum
import typing

from starlette_babel import gettext_lazy as _


AUTH_CLIENT_NAME: typing.Final[str] = "authentik"
ROLE_SYSTEM_ADMIN: typing.Final[str] = "system-admin"
ROLE_EDITOR: typing.Final[str] = "catalog-editor"
NAME_MAX_LENGTH: typing.Final[int] = 100
NAME_MIN_LENGTH: typing.Final[int] = 5
DESCRIPTION_MAX_LENGTH: typing.Final[int] = 500
DESCRIPTION_MIN_LENGTH: typing.Final[int] = 5
RELATION_MAX_LENGTH: typing.Final[int] = 50

ASSET_MAX_LINKS: typing.Final[int] = 5
PROJECT_MAX_LINKS: typing.Final[int] = 5
SURVEY_MISSION_MAX_LINKS: typing.Final[int] = 5
SURVEY_RELATED_RECORD_MAX_LINKS: typing.Final[int] = 5
SURVEY_RELATED_RECORD_MAX_ASSETS: typing.Final[int] = 20
SURVEY_RELATED_RECORD_MAX_RELATED: typing.Final[int] = 5

NEW_TOPIC_PROJECTS: typing.Final[str] = "projects"
NEW_TOPIC_SURVEY_MISSIONS: typing.Final[str] = "survey_missions"
NEW_TOPIC_SURVEY_RELATED_RECORDS: typing.Final[str] = "survey_related_records"
NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS: typing.Final[str] = (
    "asset_discovery_conigurations"
)
NEW_TOPIC_DATASET_CATEGORIES: typing.Final[str] = "dataset_categories"
NEW_TOPIC_WORKFLOW_STAGES: typing.Final[str] = "workflow_stages"

# data assets whose file is unusable without its sidecar files - these get
# downloaded as a zip bundle holding the file and all of its sidecars
BUNDLED_DATA_ASSET_EXTENSIONS: typing.Final[frozenset[str]] = frozenset({".shp"})

# data asset formats which GeoNode is able to import
GEONODE_EXPORTABLE_DATA_ASSET_EXTENSIONS: typing.Final[frozenset[str]] = frozenset(
    {".tif", ".tiff", ".gpkg", ".geojson", ".shp"}
)
# names of the GeoNode upload form fields which carry each shapefile sidecar
GEONODE_SHAPEFILE_SIDECAR_FIELDS: typing.Final[dict[str, str]] = {
    ".dbf": "dbf_file",
    ".shx": "shx_file",
    ".prj": "prj_file",
}
GEONODE_EXPORT_TIME_LIMIT_SECONDS: typing.Final[int] = 60 * 60
# a record that is under export for longer than this was abandoned by a worker
# which died mid-export, as the export task is killed at its time limit
GEONODE_EXPORT_STALE_AFTER_SECONDS: typing.Final[int] = (
    GEONODE_EXPORT_TIME_LIMIT_SECONDS + 15 * 60
)
GEONODE_EXECUTION_POLL_INTERVAL_SECONDS: typing.Final[float] = 3.0


class PageType(str, enum.Enum):
    HOME = "home"
    RESOURCE_LIST = "resource_list"
    RESOURCE_NEW = "resource_new"
    RESOURCE_UPDATE = "resource_update"
    RESOURCE_DETAIL = "resource_detail"


class ResourceType(str, enum.Enum):
    ASSET_DISCOVERY_CONFIG = "asset_discovery_configuration"
    CATEGORY = "dataset_category"
    MISSION = "survey_mission"
    PROJECT = "project"
    RECORD = "survey_related_record"
    WORKFLOW_STAGE = "workflow_stage"

    def get_topic_name(self) -> str:
        return {
            self.ASSET_DISCOVERY_CONFIG: NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
            self.CATEGORY: NEW_TOPIC_DATASET_CATEGORIES,
            self.MISSION: NEW_TOPIC_SURVEY_MISSIONS,
            self.PROJECT: NEW_TOPIC_PROJECTS,
            self.RECORD: NEW_TOPIC_SURVEY_RELATED_RECORDS,
            self.WORKFLOW_STAGE: NEW_TOPIC_WORKFLOW_STAGES,
        }[self]


class ResourceModification(str, enum.Enum):
    CREATED = "created"
    DELETED = "deleted"
    UPDATED = "updated"


class BulkResourceModification(str, enum.Enum):
    UPDATED = "updated"
    DELETED = "deleted"


class DiscoveryStage(str, enum.Enum):
    STARTED = "started"
    ENDED = "ended"
    PROGRESS = "progress"


class ValidationStage(str, enum.Enum):
    STARTED = "started"
    ENDED = "ended"


class ExportStage(str, enum.Enum):
    STARTED = "started"
    PROGRESS = "progress"
    ENDED = "ended"


class TranslatableEnumProtocol(typing.Protocol):
    def get_translated_value(self) -> str: ...


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def get_translated_value(self) -> str:
        return {
            self.PENDING: _("pending"),
            self.RUNNING: _("running"),
            self.SUCCESS: _("success"),
            self.FAILED: _("failed"),
            self.CANCELLED: _("cancelled"),
        }.get(self, self.value)


class AssetType(str, enum.Enum):
    DATA = "data"
    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"

    def get_translated_value(self) -> str:
        return {
            self.DATA: _("data"),
            self.THUMBNAIL: _("thumbnail"),
            self.PREVIEW: _("preview"),
        }.get(self, self.value)


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_DISCOVERY = "under_discovery"
    UNDER_PARSING = "under_parsing"
    UNDER_VALIDATION = "under_validation"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_DISCOVERY: _("under discovery"),
            self.UNDER_PARSING: _("under parsing"),
            self.UNDER_VALIDATION: _("under validation"),
        }.get(self, self.value)


class SurveyMissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_DISCOVERY = "under_discovery"
    UNDER_PARSING = "under_parsing"
    UNDER_VALIDATION = "under_validation"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_DISCOVERY: _("under discovery"),
            self.UNDER_PARSING: _("under parsing"),
            self.UNDER_VALIDATION: _("under validation"),
        }.get(self, self.value)


class SurveyRelatedRecordStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_DERIVATION = "under_derivation"
    UNDER_DISCOVERY = "under_discovery"
    UNDER_EXPORT = "under_export"
    UNDER_VALIDATION = "under_validation"
    UNDER_PARSING = "under_parsing"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_DERIVATION: _("under derivation"),
            self.UNDER_DISCOVERY: _("under discovery"),
            self.UNDER_EXPORT: _("under export"),
            self.UNDER_PARSING: _("under parsing"),
            self.UNDER_VALIDATION: _("under validation"),
        }.get(self, self.value)
