import enum
import typing

AUTH_CLIENT_NAME: typing.Final[str] = "authentik"


class MarineCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
