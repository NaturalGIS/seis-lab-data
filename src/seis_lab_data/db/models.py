import datetime as dt
import json
import uuid
from functools import partial
from typing import (
    Annotated,
    TypedDict,
)

import shapely
from geoalchemy2 import (
    Geometry,
    WKBElement,
)
from pydantic import (
    ConfigDict,
    PlainSerializer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    Column,
    Date,
    DateTime,
    Field,
    func,
    SQLModel,
    Relationship,
)

from .. import constants

now_ = partial(dt.datetime.now, tz=dt.timezone.utc)


class ValidationError(TypedDict):
    name: str
    type_: str
    message: str


class ValidationResult(TypedDict):
    is_valid: bool
    errors: list[ValidationError] | None


class LocalizableString(TypedDict):
    locale: str


def serialize_wkbelement(wkbelement: WKBElement):
    geom = shapely.from_wkb(bytes(wkbelement.data))
    return json.loads(shapely.to_geojson(geom))


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
    link_description: LocalizableString


class DatasetCategory(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="dataset_category",
    )


class DomainType(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="domain_type",
    )


class WorkflowStage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )

    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="workflow_stage",
    )


class Project(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    status: constants.ProjectStatus = constants.ProjectStatus.DRAFT
    root_path: str = ""
    is_valid: bool = False
    validation_result: ValidationResult = Field(sa_column=Column(JSONB))
    links: Annotated[list[Link], PlainSerializer(serialize_localizable_field)] = Field(
        sa_column=Column(JSONB), default_factory=list
    )
    bbox_4326: Annotated[
        WKBElement,
        PlainSerializer(serialize_wkbelement, return_type=dict, when_used="json"),
    ] = Field(
        sa_column=Column(
            Geometry(
                srid=4326,
                geometry_type="POLYGON",
                spatial_index=True,
            ),
        )
    )
    created_at: dt.datetime | None = Field(default_factory=now_)
    updated_at: dt.datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )
    temporal_extent_begin: dt.date | None = Field(sa_column=Column(Date()))
    temporal_extent_end: dt.date | None = Field(sa_column=Column(Date()))

    survey_missions: list["SurveyMission"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class SurveyMission(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    links: Annotated[list[Link], PlainSerializer(serialize_localizable_field)] = Field(
        sa_column=Column(JSONB), default_factory=list
    )
    relative_path: str = ""
    status: constants.SurveyMissionStatus = constants.SurveyMissionStatus.DRAFT
    is_valid: bool = False
    validation_result: ValidationResult = Field(sa_column=Column(JSONB))
    bbox_4326: Annotated[
        WKBElement,
        PlainSerializer(serialize_wkbelement, return_type=dict, when_used="json"),
    ] = Field(
        sa_column=Column(
            Geometry(
                srid=4326,
                geometry_type="POLYGON",
                spatial_index=True,
            ),
        )
    )
    created_at: dt.datetime | None = Field(default_factory=now_)
    updated_at: dt.datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )
    temporal_extent_begin: dt.date | None = Field(sa_column=Column(Date()))
    temporal_extent_end: dt.date | None = Field(sa_column=Column(Date()))

    project: Project = Relationship(back_populates="survey_missions")
    survey_related_records: list["SurveyRelatedRecord"] = Relationship(
        back_populates="survey_mission",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class SurveyRelatedRecord(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner: str = Field(max_length=100, index=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    status: constants.SurveyRelatedRecordStatus = (
        constants.SurveyRelatedRecordStatus.DRAFT
    )
    is_valid: bool = False
    validation_result: ValidationResult = Field(sa_column=Column(JSONB))
    survey_mission_id: uuid.UUID = Field(
        foreign_key="surveymission.id", ondelete="CASCADE"
    )
    dataset_category_id: uuid.UUID | None = Field(
        foreign_key="datasetcategory.id", default=None, ondelete="SET NULL"
    )
    domain_type_id: uuid.UUID | None = Field(
        foreign_key="domaintype.id", default=None, ondelete="SET NULL"
    )
    workflow_stage_id: uuid.UUID | None = Field(
        foreign_key="workflowstage.id", default=None, ondelete="SET NULL"
    )
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
    bbox_4326: Annotated[
        WKBElement,
        PlainSerializer(serialize_wkbelement, return_type=dict, when_used="json"),
    ] = Field(
        sa_column=Column(
            Geometry(
                srid=4326,
                geometry_type="POLYGON",
                spatial_index=True,
            ),
        )
    )
    created_at: dt.datetime | None = Field(default_factory=now_)
    updated_at: dt.datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )
    temporal_extent_begin: dt.date | None = Field(sa_column=Column(Date()))
    temporal_extent_end: dt.date | None = Field(sa_column=Column(Date()))
    assets: list["RecordAsset"] = Relationship(
        back_populates="survey_related_record",
        sa_relationship_kwargs={
            # "cascade": "all, delete-orphan",
            "cascade": "save-update, merge, expunge, delete, delete-orphan",
            "passive_deletes": True,
        },
    )


class RecordAsset(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Annotated[LocalizableString, PlainSerializer(serialize_localizable_field)] = (
        Field(sa_column=Column(JSONB))
    )
    description: Annotated[
        LocalizableString, PlainSerializer(serialize_localizable_field)
    ] = Field(sa_column=Column(JSONB))
    is_valid: bool = False
    survey_related_record_id: uuid.UUID = Field(
        foreign_key="surveyrelatedrecord.id", ondelete="CASCADE"
    )
    relative_path: str = ""
    links: Annotated[list[Link], PlainSerializer(serialize_localizable_field)] = Field(
        sa_column=Column(JSONB), default_factory=list
    )
    survey_related_record: SurveyRelatedRecord = Relationship(
        back_populates="assets",
    )
