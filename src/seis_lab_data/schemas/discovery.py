import typing
import pydantic

from .common import LinkSchema


RecordDiscoveryConfId = typing.NewType("RecordDiscoveryConfId", str)
TemplatedString = typing.NewType("TemplatedString", str)
TranslatableString = typing.NewType("TranslatableString", dict[str, TemplatedString])


class RecordAssetDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    description: TranslatableString | None
    discovery_patterns: list[TemplatedString]
    links: list[LinkSchema]
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]


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
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]

    @classmethod
    def from_raw_config(
        cls,
        raw_identifier: str,
        raw_config: dict,
    ) -> "SurveyRecordDiscoveryConfiguration":
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
                    extra_context=a.get("extra_context", {}),
                )
                for a in raw_config["assets"]
            ],
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            extra_context=dict(raw_config.get("extra_context", {})),
        )


class SurveyMissionDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    discovery_pattern: TemplatedString
    description: TranslatableString | None = None
    links: list[LinkSchema]
    record_configuration_ids: list[RecordDiscoveryConfId]
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]

    @classmethod
    def from_raw_config(
        cls,
        raw_config: dict,
    ) -> "SurveyMissionDiscoveryConfiguration":
        return cls(
            name=TranslatableString(dict(raw_config.get("name"))),
            description=TranslatableString(dict(raw_config.get("description"))),
            discovery_pattern=TemplatedString(raw_config["discovery_pattern"]),
            links=[LinkSchema(**li) for li in raw_config.get("links", [])],
            record_configuration_ids=raw_config.get("records", []),
            extra_context=dict(raw_config.get("extra_context", {})),
        )


class ProjectDiscoveryConfiguration(pydantic.BaseModel):
    survey_missions: list[SurveyMissionDiscoveryConfiguration]
    links: list[LinkSchema]
    records: dict[RecordDiscoveryConfId, SurveyRecordDiscoveryConfiguration]
    record_relations: list[RecordRelationDiscoveryConfiguration]
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]

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
            extra_context=raw_config.get("extra_context", {}),
        )
