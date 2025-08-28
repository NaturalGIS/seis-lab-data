import uuid
from typing import TypedDict

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    Column,
    Field,
    SQLModel,
    Relationship,
)

from ..constants import MarineCampaignStatus


class LocalizableString(TypedDict):
    locale: str


class Link(TypedDict):
    url: str
    media_type: str
    relation: str
    description: LocalizableString


class MarineCampaign(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str
    status: MarineCampaignStatus = MarineCampaignStatus.DRAFT
    is_valid: bool = False
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)

    survey_missions: list["SurveyMission"] = Relationship(
        back_populates="marine_campaign",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class SurveyMission(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str
    marine_campaign_id: uuid.UUID = Field(foreign_key="marinecampaign.id")
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)
    marine_campaign: MarineCampaign = Relationship(back_populates="survey_missions")
    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="survey_mission",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class SurveyRelatedRecord(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str
    survey_mission_id: uuid.UUID = Field(foreign_key="surveymission.id")
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)
    survey_mission: SurveyMission = Relationship(
        back_populates="survey_related_records"
    )
