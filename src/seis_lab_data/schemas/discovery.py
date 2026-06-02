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


def _parse_property_handler_from_raw(name: str, raw: dict) -> "PropertyHandler":
    """Parse a property handler from the {extractor, matcher} JSON config format."""
    extractor = raw.get("extractor", {})
    matcher = raw.get("matcher", {})
    prop_type = matcher.get("type")
    pattern = extractor.get("pattern")
    if prop_type == "datetime":
        kwargs: dict = {
            "type": "datetime",
            "delta_below_seconds": matcher["delta_below_seconds"],
        }
        if pattern:
            kwargs["pattern"] = pattern
        return DatetimeProperty(**kwargs)
    elif prop_type == "constant":
        kwargs = {
            "type": "constant",
            "choices": matcher["choices"],
            "match_type": matcher["match_type"],
        }
        if pattern:
            kwargs["pattern"] = pattern
        return ConstantProperty(**kwargs)
    else:
        raise ValueError(f"Unknown property type {prop_type!r} for property {name!r}")


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
        return isinstance(value, dt.date)

    def is_compatible(self, a: dt.date, b: dt.date) -> bool:
        return abs((a - b).total_seconds()) < self.delta_below_seconds


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

    def is_compatible(self, a: str, b: str) -> bool:
        return a == b


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

    def is_compatible(self, a, b) -> bool:
        return self.handler.is_compatible(a, b)

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


class DiscoveredRecord(pydantic.BaseModel):
    """A group of files (one per asset type) that share the same property values."""

    properties: dict[
        str, object
    ]  # the shared property values that identify this record
    assets: dict[int, DiscoveredFile]  # asset index -> DiscoveredFile


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
        # Parse extra_properties from the {extractor, matcher} JSON format
        asset_extra_props: dict[str, PropertyHandler] = {}
        record_extra_props: list[RecordProperty] = []
        for k, v in raw_config.get("extra_properties", {}).items():
            handler = _parse_property_handler_from_raw(k, v)
            asset_extra_props[k] = handler
            record_extra_props.append(RecordProperty(identifier=k, handler=handler))

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
                    extra_properties=asset_extra_props,
                )
                for a in raw_config["assets"]
            ],
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            extra_properties=record_extra_props if record_extra_props else None,
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
