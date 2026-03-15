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
    links: list[LinkSchema] | None = None
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]


class RecordRelationDiscoveryConfiguration(pydantic.BaseModel):
    relation_name: str
    related_record: RecordDiscoveryConfId


class SurveyRecordDiscoveryConfiguration(pydantic.BaseModel):
    id_: RecordDiscoveryConfId
    dataset_category: str
    domain_type: str
    workflow_stage: str
    name: TranslatableString
    description: TranslatableString | None
    assets: list[RecordAssetDiscoveryConfiguration]
    relations: list[RecordRelationDiscoveryConfiguration]
    links: list[LinkSchema] | None = None
    # these can become tags in the generated record, to be searchable
    # they can also be used as placeholders when building the filesystem search template
    extra_context: dict[str, str]

    @classmethod
    def from_raw_config(
        cls,
        raw_identifier: str,
        raw_record_config: dict,
        raw_relations_config: list[dict] | None = None,
    ) -> "SurveyRecordDiscoveryConfiguration":
        return cls(
            id_=RecordDiscoveryConfId(raw_identifier),
            dataset_category=raw_record_config["dataset_category"],
            domain_type=raw_record_config["domain_type"],
            workflow_stage=raw_record_config["workflow_stage"],
            name=TranslatableString(dict(raw_record_config["name"])),
            description=(
                TranslatableString(dict(desc))
                if (desc := raw_record_config.get("description")) is not None
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
                    extra_context=a.get("extra_context", {}),
                )
                for a in raw_record_config["assets"]
            ],
            relations=[
                RecordRelationDiscoveryConfiguration(
                    relation_name=r[2], related_record=r[1]
                )
                for r in raw_relations_config
                if r[0] == raw_identifier
            ]
            if raw_relations_config is not None
            else [],
            links=raw_record_config.get("links"),
            extra_context=dict(raw_record_config.get("extra_context", {})),
        )


class SurveyMissionDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    description: TranslatableString | None
    discovery_pattern: TemplatedString
    links: list[LinkSchema] | None = None
    records: list[SurveyRecordDiscoveryConfiguration]
    extra_context: dict[str, str]

    @classmethod
    def from_raw_config(
        cls,
        raw_survey_config: dict,
        raw_records_config: dict,
        raw_relations_config: list[dict] | None = None,
    ) -> "SurveyMissionDiscoveryConfiguration":
        return cls(
            name=TranslatableString(dict(raw_survey_config.get("name"))),
            description=TranslatableString(dict(raw_survey_config.get("description"))),
            discovery_pattern=TemplatedString(raw_survey_config["discovery_pattern"]),
            links=raw_survey_config.get("links"),
            records=[
                SurveyRecordDiscoveryConfiguration.from_raw_config(
                    id_, raw_records_config[id_], raw_relations_config
                )
                for id_ in raw_survey_config.get("records", [])
            ],
            extra_context=dict(raw_survey_config.get("extra_context", {})),
        )


class ProjectDiscoveryConfiguration(pydantic.BaseModel):
    survey_missions: list[SurveyMissionDiscoveryConfiguration]

    @classmethod
    def from_raw_config(cls, raw_config: dict) -> "ProjectDiscoveryConfiguration":
        survey_confs = []
        for raw_survey_config in raw_config.get("survey_missions", []):
            survey_confs.append(
                SurveyMissionDiscoveryConfiguration.from_raw_config(
                    raw_survey_config,
                    raw_config.get("records", {}),
                    raw_config.get("relations", []),
                )
            )
        return cls(survey_missions=survey_confs)
