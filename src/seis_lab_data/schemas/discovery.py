import typing
import pydantic


RecordDiscoveryConfId = typing.NewType("RecordDiscoveryConfId", str)
TemplatedString = typing.NewType("TemplatedString", str)
TranslatableString = typing.NewType("TranslatableString", dict[str, TemplatedString])


class RecordAssetDiscoveryConfiguration(pydantic.BaseModel):
    name: TranslatableString
    description: TranslatableString | None
    discovery_patterns: list[TemplatedString]


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
    extra_context: dict[str, str]

    @classmethod
    def from_raw_config(
        cls,
        raw_identifier: str,
        raw_record_config: dict,
        raw_relations_config: list[dict],
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
                )
                for a in raw_record_config["assets"]
            ],
            relations=[
                RecordRelationDiscoveryConfiguration(
                    relation_name=r[2], related_record=r[1]
                )
                for r in raw_relations_config
                if r[0] == raw_identifier
            ],
            extra_context=dict(raw_record_config.get("extra_context", {})),
        )
