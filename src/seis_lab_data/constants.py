import enum
import typing

from starlette_babel import gettext_lazy as _

AUTH_CLIENT_NAME: typing.Final[str] = "authentik"
MAX_NAME_LENGTH: typing.Final[int] = 100
MAX_DESCRIPTION_LENGTH: typing.Final[int] = 500


class TranslatableEnumProtocol(typing.Protocol):
    def get_translated_value(self) -> str: ...


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
        }.get(self, self.value)


class SurveyMissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
        }.get(self, self.value)


class SurveyRelatedRecordStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

    def get_translated_value(self) -> str:
        return {
            self.DRAFT: _("draft"),
            self.PUBLISHED: _("published"),
        }.get(self, self.value)
