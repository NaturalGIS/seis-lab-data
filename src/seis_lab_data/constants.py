import enum
import typing

AUTH_CLIENT_NAME: typing.Final[str] = "authentik"
MAX_NAME_LENGTH: typing.Final[int] = 100
MAX_DESCRIPTION_LENGTH: typing.Final[int] = 500


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class SurveyMissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class SurveyRelatedRecordStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
