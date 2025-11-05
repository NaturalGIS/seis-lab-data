import enum
import typing

from starlette_babel import gettext_lazy as _


ASSET_MAX_LINKS: typing.Final[int] = 5
AUTH_CLIENT_NAME: typing.Final[str] = "authentik"
NAME_MAX_LENGTH: typing.Final[int] = 100
NAME_MIN_LENGTH: typing.Final[int] = 5
DESCRIPTION_MAX_LENGTH: typing.Final[int] = 500
DESCRIPTION_MIN_LENGTH: typing.Final[int] = 5
PROJECT_MAX_LINKS: typing.Final[int] = 5
SURVEY_MISSION_MAX_LINKS: typing.Final[int] = 5
SURVEY_RELATED_RECORD_MAX_ASSETS: typing.Final[int] = 20

PROGRESS_TOPIC_NAME_TEMPLATE: typing.Final[str] = "progress:{request_id}"

PROJECT_UPDATED_TOPIC: typing.Final[str] = "updated:{project_id}"
PROJECT_STATUS_CHANGED_TOPIC: typing.Final[str] = "status-changed:{project_id}"
PROJECT_VALIDITY_CHANGED_TOPIC: typing.Final[str] = "validity-changed:{project_id}"
PROJECT_DELETED_TOPIC: typing.Final[str] = "deleted:{project_id}"


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


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_PARSING = "under_parsing"
    UNDER_VALIDATION = "under_validation"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_PARSING: _("under_parsing"),
            self.UNDER_VALIDATION: _("under_validation"),
        }.get(self, self.value)


class SurveyMissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_PARSING = "under_parsing"
    UNDER_VALIDATION = "under_validation"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_PARSING: _("under_parsing"),
            self.UNDER_VALIDATION: _("under_validation"),
        }.get(self, self.value)


class SurveyRelatedRecordStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_DERIVATION = "under_derivation"
    UNDER_EXPORT = "under_export"
    UNDER_VALIDATION = "under_validation"
    UNDER_PARSING = "under_parsing"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
            self.UNDER_DERIVATION: _("under_derivation"),
            self.UNDER_EXPORT: _("under_export"),
            self.UNDER_PARSING: _("under_parsing"),
            self.UNDER_VALIDATION: _("under_validation"),
        }.get(self, self.value)
