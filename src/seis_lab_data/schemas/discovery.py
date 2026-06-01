import datetime as dt
import typing
from typing import (
    Annotated,
    Literal,
    Union,
)

import pydantic
from typing_extensions import Self

from .common import LinkSchema


RecordDiscoveryConfId = typing.NewType("RecordDiscoveryConfId", str)
TemplatedString = typing.NewType("TemplatedString", str)
TranslatableString = typing.NewType("TranslatableString", dict[str, TemplatedString])


class DatetimeProperty(pydantic.BaseModel):
    type_: Annotated[Literal["datetime"], pydantic.Field(validation_alias="type")]
    pattern: str = r"\d{8}"  # sensible default
    delta_below_seconds: int

    def convert(self, raw: str) -> dt.date:
        return dt.datetime.strptime(raw, "%Y%m%d").date()

    def validate_value(self, value: dt.date) -> bool:
        return abs((dt.date.today() - value).total_seconds()) < self.delta_below_seconds


class ConstantProperty(pydantic.BaseModel):
    type_: Annotated[Literal["constant"], pydantic.Field(validation_alias="type")]
    pattern: str = r"\w+"  # sensible default, overridable
    choices: list[str]
    match_type: Literal["equal", "any"]

    def convert(self, raw: str) -> str:
        return raw

    def validate_value(self, value: str) -> bool:
        if self.match_type == "equal":
            return value in self.choices
        return any(c in value for c in self.choices)


PropertyHandler = Annotated[
    Union[DatetimeProperty, ConstantProperty], pydantic.Field(discriminator="type_")
]


class RecordProperty(pydantic.BaseModel):
    identifier: str  # this needs to be a valid python identifier, as we will use it to build a regexp identifier
    handler: PropertyHandler

    def convert(self, raw: str):
        return self.handler.convert(raw)

    def validate_value(self, value) -> bool:
        return self.handler.validate_value(value)

    @property
    def pattern(self) -> str:
        return self.handler.pattern


class RecordAssetDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    description: TranslatableString | None
    discovery_patterns: list[TemplatedString]
    links: list[LinkSchema]
    extra_properties: dict[str, PropertyHandler]
    _properties: dict[str, RecordProperty]

    @pydantic.model_validator(mode="after")
    def _inject_identifiers(self) -> Self:
        # Wrap each handler in a RecordProperty, injecting the dict key
        self._properties: dict[str, RecordProperty] = {
            key: RecordProperty(identifier=key, handler=handler)
            for key, handler in self.extra_properties.items()
        }
        return self

    @property
    def properties(self) -> dict[str, RecordProperty]:
        return self._properties


class DiscoveredFile(pydantic.BaseModel):
    path: str
    properties: dict[str, object]  # identifier -> converted value


class RecordRelationDiscoveryConfiguration(pydantic.BaseModel):
    subject_record_id: RecordDiscoveryConfId
    related_record_id: RecordDiscoveryConfId
    relation_name: str


class SurveyRecordDiscoveryConfiguration(pydantic.BaseModel):
    id_: RecordDiscoveryConfId
    dataset_category: str
    domain_type: str
    workflow_stage: str
    name: TranslatableString
    description: TranslatableString | None
    assets: list[RecordAssetDiscoveryConfiguration]
    links: list[LinkSchema]
    extra_properties: list[RecordProperty] | None = None

    @classmethod
    def from_raw_config(
        cls,
        raw_identifier: str,
        raw_config: dict,
    ) -> "SurveyRecordDiscoveryConfiguration":
        extra_properties = (
            [
                RecordProperty(identifier=k, **raw_props)
                for k, raw_props in extra.items()
            ]
            if (extra := raw_config.get("extra_properties")) is not None
            else None
        )
        return cls(
            id_=RecordDiscoveryConfId(raw_identifier),
            dataset_category=raw_config["dataset_category"],
            domain_type=raw_config["domain_type"],
            workflow_stage=raw_config["workflow_stage"],
            name=TranslatableString(dict(raw_config["name"])),
            description=(
                TranslatableString(dict(desc))
                if (desc := raw_config.get("description")) is not None
                else None
            ),
            assets=[
                RecordAssetDiscoveryConfiguration(
                    name=TranslatableString(a["name"]),
                    description=(
                        TranslatableString(desc)
                        if (desc := a.get("description")) is not None
                        else None
                    ),
                    discovery_patterns=list(a["discovery_patterns"]),
                    links=[LinkSchema(**li) for li in a.get("links", [])],
                    extra_properties=extra_properties,
                )
                for a in raw_config["assets"]
            ],
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            extra_properties=extra_properties,
        )


class SurveyMissionDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    # survey mission config's path is not supposed to be a pattern, but rather a simple string
    relative_path: str
    description: TranslatableString | None = None
    links: list[LinkSchema]
    record_configuration_ids: list[RecordDiscoveryConfId]

    @classmethod
    def from_raw_config(
        cls,
        raw_config: dict,
    ) -> "SurveyMissionDiscoveryConfiguration":
        return cls(
            name=TranslatableString(dict(raw_config.get("name"))),
            description=TranslatableString(dict(raw_config.get("description"))),
            relative_path=raw_config.get("relative_path", "/").strip("/"),
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            record_configuration_ids=raw_config.get("records", []),
        )


class ProjectDiscoveryConfiguration(pydantic.BaseModel):
    survey_missions: list[SurveyMissionDiscoveryConfiguration]
    links: list[LinkSchema]
    records: dict[RecordDiscoveryConfId, SurveyRecordDiscoveryConfiguration]
    record_relations: list[RecordRelationDiscoveryConfiguration]

    @classmethod
    def from_raw_config(cls, raw_config: dict) -> "ProjectDiscoveryConfiguration":
        return cls(
            survey_missions=[
                SurveyMissionDiscoveryConfiguration.from_raw_config(m)
                for m in raw_config.get("survey_missions", [])
            ],
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            records={
                rec_id: SurveyRecordDiscoveryConfiguration.from_raw_config(
                    rec_id, rec_conf
                )
                for rec_id, rec_conf in raw_config.get("records", {}).items()
            },
            record_relations=[
                RecordRelationDiscoveryConfiguration(
                    subject_record_id=RecordDiscoveryConfId(rel_conf[0]),
                    related_record_id=RecordDiscoveryConfId(rel_conf[1]),
                    relation_name=rel_conf[2],
                )
                for rel_conf in raw_config.get("record_relations", [])
            ],
        )
