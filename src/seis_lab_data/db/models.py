import uuid
from typing import TypedDict

from pydantic import field_serializer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    Column,
    Field,
    SQLModel,
    Relationship,
)

from ..constants import (
    MarineCampaignStatus,
    SurveyMissionStatus,
    SurveyRelatedRecordStatus,
)


class LocalizableString(TypedDict):
    locale: str


class Link(TypedDict):
    url: str
    media_type: str
    relation: str
    description: LocalizableString


class DatasetCategory(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="dataset_category",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class DomainType(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="domain_type",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class WorkflowStage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="workflow_stage",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class MarineCampaign(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=50, index=True, unique=True)
    status: MarineCampaignStatus = MarineCampaignStatus.DRAFT
    root_path: str = ""
    is_valid: bool = False
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)

    survey_missions: list["SurveyMission"] = Relationship(
        back_populates="marine_campaign",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class SurveyMission(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=50, index=True, unique=True)
    marine_campaign_id: uuid.UUID = Field(foreign_key="marinecampaign.id")
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)
    marine_campaign: MarineCampaign = Relationship(back_populates="survey_missions")
    status: SurveyMissionStatus = SurveyMissionStatus.DRAFT
    is_valid: bool = False
    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="survey_mission",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class SurveyRelatedRecord(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=50, index=True, unique=True)
    status: SurveyRelatedRecordStatus = SurveyRelatedRecordStatus.DRAFT
    is_valid: bool = False
    survey_mission_id: uuid.UUID = Field(foreign_key="surveymission.id")
    dataset_category_id: uuid.UUID = Field(foreign_key="datasetcategory.id")
    domain_type_id: uuid.UUID = Field(foreign_key="domaintype.id")
    workflow_stage_id: uuid.UUID = Field(foreign_key="workflowstage.id")
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)
    survey_mission: SurveyMission = Relationship(
        back_populates="survey_related_records"
    )
    dataset_category: DatasetCategory = Relationship(
        back_populates="survey_related_records"
    )
    domain_type: DomainType = Relationship(back_populates="survey_related_records")
    workflow_stage: WorkflowStage = Relationship(
        back_populates="survey_related_records"
    )
    assets: list["RecordAsset"] = Relationship(
        back_populates="survey_related_record",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class RecordAsset(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    survey_related_record_id: uuid.UUID = Field(foreign_key="surveyrelatedrecord.id")
    name: LocalizableString = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=50, index=True, unique=True)

    survey_related_record: SurveyRelatedRecord = Relationship(back_populates="assets")

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name
