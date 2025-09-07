import enum
import typing

from starlette_babel import gettext_lazy as _

AUTH_CLIENT_NAME: typing.Final[str] = "authentik"
NAME_MAX_LENGTH: typing.Final[int] = 100
NAME_MIN_LENGTH: typing.Final[int] = 5
DESCRIPTION_MAX_LENGTH: typing.Final[int] = 500
DESCRIPTION_MIN_LENGTH: typing.Final[int] = 5


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
