import uuid
from typing import (
    Annotated,
    TypedDict,
)

from pydantic import (
    PlainSerializer,
    field_serializer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    Column,
    Field,
    SQLModel,
    Relationship,
)

from .. import constants


class LocalizableString(TypedDict):
    locale: str


def serialize_localizable_field(value: LocalizableString, _info):
    """Serialize a localizable field.

    Localizable fields use a JSONB type, which is not serialized by default, hence
    the need for this function.
    """
    return value


class Link(TypedDict):
    url: str
    media_type: str
    relation: str
    description: LocalizableString


class DatasetCategory(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="dataset_category",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class DomainType(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="domain_type",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class WorkflowStage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="workflow_stage",
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name


class Project(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=constants.MAX_NAME_LENGTH, index=True, unique=True)
    status: constants.ProjectStatus = constants.ProjectStatus.DRAFT
    root_path: str = ""
    is_valid: bool = False
    links: list[Link] = Field(sa_column=Column(JSONB), default_factory=list)

    survey_missions: list["SurveyMission"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )

    @field_serializer("name")
    def serialize_name(self, name: LocalizableString, _info):
        return name

    @field_serializer("description")
    def serialize_description(self, description: LocalizableString, _info):
        return description

    @field_serializer("links")
    def serialize_links(self, links: list[Link], _info):
        return links


class SurveyMission(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=constants.MAX_NAME_LENGTH, index=True, unique=True)
    project_id: uuid.UUID = Field(foreign_key="project.id")
    links: Annotated[list[Link], PlainSerializer(serialize_localizable_field)] = Field(
        sa_column=Column(JSONB), default_factory=list
    )
    relative_path: str = ""
    status: constants.SurveyMissionStatus = constants.SurveyMissionStatus.DRAFT
    is_valid: bool = False

    project: Project = Relationship(back_populates="survey_missions")
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
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=constants.MAX_NAME_LENGTH, index=True, unique=True)
    status: constants.SurveyRelatedRecordStatus = (
        constants.SurveyRelatedRecordStatus.DRAFT
    )
    is_valid: bool = False
    survey_mission_id: uuid.UUID = Field(foreign_key="surveymission.id")
    dataset_category_id: uuid.UUID = Field(foreign_key="datasetcategory.id")
    domain_type_id: uuid.UUID = Field(foreign_key="domaintype.id")
    workflow_stage_id: uuid.UUID = Field(foreign_key="workflowstage.id")
    links: Annotated[list[Link], PlainSerializer(serialize_localizable_field)] = Field(
        sa_column=Column(JSONB), default_factory=list
    )
    relative_path: str = ""
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


class RecordAsset(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    survey_related_record_id: uuid.UUID = Field(foreign_key="surveyrelatedrecord.id")
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    slug: str = Field(max_length=constants.MAX_NAME_LENGTH, index=True, unique=True)
    survey_related_record: SurveyRelatedRecord = Relationship(back_populates="assets")
