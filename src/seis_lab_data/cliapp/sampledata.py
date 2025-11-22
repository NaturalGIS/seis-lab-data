import datetime as dt
import random
import uuid
from itertools import count
from typing import (
    Iterator,
    Sequence,
)

import pydantic
import shapely
from faker import Faker

from .. import schemas
from ..db import models

_FAKE_EN = Faker("en_US")
_FAKE_PT = Faker("pt_PT")

_owner_id = schemas.UserId("fake-owner1")
_my_first_project_id = schemas.ProjectId(
    uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3")
)
_my_second_project_id = schemas.ProjectId(
    uuid.UUID("9a877fbe-da98-45ab-af70-711879c6fc01")
)

_my_first_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("cfe10cd8-5a5e-40e4-807b-7064f94a2edf")
)
_my_second_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("38d9ad16-6cf5-4c64-abfe-0915c6c22268")
)
_my_third_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("ebedf3e5-38a4-42ad-bb60-52b4eee6bd54")
)
_my_fourth_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("03a5f8c1-60ba-4309-a06a-e7b0c8851f20")
)
_my_fifth_survey_mission_id = schemas.SurveyMissionId(
    uuid.UUID("51a44e56-42e7-4aab-a1c7-659436df99c1")
)


def get_projects_to_create() -> list[schemas.ProjectCreate]:
    return [
        schemas.ProjectCreate(
            id=_my_first_project_id,
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="My first project", pt="O meu primeiro projeto"
            ),
            description=schemas.LocalizableDraftDescription(
                en="A Fake description for my first project",
                pt="Uma descrição falsa para o meu primeiro projeto",
            ),
            root_path="/projects/first",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for link",
                        pt="Uma descrição falsa para o link",
                    ),
                ),
            ],
        ),
        schemas.ProjectCreate(
            id=_my_second_project_id,
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="My second project", pt="O meu segundo projeto"
            ),
            description=schemas.LocalizableDraftDescription(
                en="A fake description for my second project",
                pt="Uma descrição sintética para o meu segundo projeto",
            ),
            root_path="/projects/second",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for link",
                        pt="Uma descrição falsa para o link",
                    ),
                )
            ],
        ),
    ]


def get_survey_missions_to_create() -> list[schemas.SurveyMissionCreate]:
    return [
        schemas.SurveyMissionCreate(
            id=_my_first_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My first survey mission", pt="A minha primeira missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my first survey mission",
                pt="Esta é a descrição para a minha primeira missão",
            ),
            relative_path="mission1",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_second_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My second survey mission", pt="A minha segunda missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my second survey mission",
                pt="Esta é a descrição para a minha segunda missão",
            ),
            relative_path="mission2",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_third_survey_mission_id,
            owner=_owner_id,
            project_id=_my_first_project_id,
            name=schemas.LocalizableDraftName(
                en="My third survey mission", pt="A minha terceira missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my third survey mission",
                pt="Esta é a descrição para a minha terceira missão",
            ),
            relative_path="mission3",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_fourth_survey_mission_id,
            owner=_owner_id,
            project_id=_my_second_project_id,
            name=schemas.LocalizableDraftName(
                en="My fourth survey mission", pt="A minha quarta missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my fourth survey mission",
                pt="Esta é a descrição para a minha quarta missão",
            ),
            relative_path="mission4",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
        schemas.SurveyMissionCreate(
            id=_my_fifth_survey_mission_id,
            owner=_owner_id,
            project_id=_my_second_project_id,
            name=schemas.LocalizableDraftName(
                en="My fifth survey mission", pt="A minha quinta missão"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is the description for my fifth survey mission",
                pt="Esta é a descrição para a minha quinta missão",
            ),
            relative_path="mission5",
            links=[
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl1.com"),
                    media_type="text/html",
                    relation="related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the first link",
                        pt="Uma descrição falsa para o primeiro link",
                    ),
                ),
                schemas.LinkSchema(
                    url=pydantic.AnyHttpUrl("https://fakeurl2.com"),
                    media_type="text/html",
                    relation="also-related",
                    link_description=schemas.LocalizableDraftDescription(
                        en="A fake description for the second link",
                        pt="Uma descrição falsa para o segundo link",
                    ),
                ),
            ],
        ),
    ]


def get_survey_related_records_to_create(
    dataset_categories: dict[str, models.DatasetCategory],
    domain_types: dict[str, models.DomainType],
    workflow_stages: dict[str, models.WorkflowStage],
) -> list[schemas.SurveyRelatedRecordCreate]:
    return [
        schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(
                uuid.UUID("f49d678b-f11a-4798-92dc-604883bc8bda")
            ),
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="First record",
                pt="Primeiro registo",
            ),
            description=schemas.LocalizableDraftDescription(
                en="Description for first record",
                pt="Descrição do primeiro registo",
            ),
            survey_mission_id=_my_first_survey_mission_id,
            dataset_category_id=schemas.DatasetCategoryId(
                dataset_categories["bathymetry"].id
            ),
            domain_type_id=schemas.DomainTypeId(domain_types["geophysical"].id),
            workflow_stage_id=schemas.WorkflowStageId(workflow_stages["raw data"].id),
            relative_path="first-record",
            links=[],
            assets=[
                schemas.RecordAssetCreate(
                    id=schemas.SurveyRelatedRecordId(
                        uuid.UUID("85f4683c-7d4a-444c-8896-04278bc89e63")
                    ),
                    name=schemas.LocalizableDraftName(
                        en="First asset",
                        pt="Primeiro recurso",
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en="Description for first asset",
                        pt="Descrição do primeiro recurso",
                    ),
                    relative_path="first-asset",
                    links=[],
                ),
                schemas.RecordAssetCreate(
                    id=schemas.SurveyRelatedRecordId(
                        uuid.UUID("a9eca3df-03ba-4f46-a98d-3e30139eb035")
                    ),
                    name=schemas.LocalizableDraftName(
                        en="Second asset",
                        pt="Segundo recurso",
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en="Description for second asset",
                        pt="Descrição do segundo recurso",
                    ),
                    relative_path="second-asset",
                    links=[],
                ),
            ],
        ),
        schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(
                uuid.UUID("c51e0d11-c4c4-4b4f-8d04-2a115196ff04")
            ),
            owner=_owner_id,
            name=schemas.LocalizableDraftName(
                en="Second record",
                pt="Segundo registo",
            ),
            description=schemas.LocalizableDraftDescription(
                en="Description for second record",
                pt="Descrição do segundo registo",
            ),
            survey_mission_id=_my_second_survey_mission_id,
            dataset_category_id=schemas.DatasetCategoryId(
                dataset_categories["bathymetry"].id
            ),
            domain_type_id=schemas.DomainTypeId(domain_types["geophysical"].id),
            workflow_stage_id=schemas.WorkflowStageId(workflow_stages["raw data"].id),
            relative_path="second-record",
            links=[],
            assets=[
                schemas.RecordAssetCreate(
                    id=schemas.SurveyRelatedRecordId(
                        uuid.UUID("a53728ed-5422-4f08-806f-3e75bbb1b3e8")
                    ),
                    name=schemas.LocalizableDraftName(
                        en="Third asset",
                        pt="Terceiro recurso",
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en="Description for third asset",
                        pt="Descrição do terceiro recurso",
                    ),
                    relative_path="third-asset",
                    links=[],
                ),
                schemas.RecordAssetCreate(
                    id=schemas.SurveyRelatedRecordId(
                        uuid.UUID("bd4bed96-43bd-4d5c-a7b2-d04461dfb23c")
                    ),
                    name=schemas.LocalizableDraftName(
                        en="Fourth asset",
                        pt="Quarto recurso",
                    ),
                    description=schemas.LocalizableDraftDescription(
                        en="Description for fourth asset",
                        pt="Descrição do quarto recurso",
                    ),
                    relative_path="fourth-asset",
                    links=[],
                ),
            ],
        ),
    ]


def generate_sample_projects(
    owners: Sequence[schemas.UserId],
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
    root_path: str = "/archive",
) -> Iterator[
    tuple[
        schemas.ProjectCreate,
        list[
            tuple[schemas.SurveyMissionCreate, list[schemas.SurveyRelatedRecordCreate]]
        ],
    ],
]:
    """Generate large numbers of sample projects, for development and testingpurposes.

    All projects will be generated with a `_sample` suffix in their english name.
    """
    for _ in count():
        links = (
            [next(generate_sample_link()) for _ in range(_FAKE_EN.random_int(0, 15))]
            if _FAKE_EN.random_digit() < 5
            else []
        )
        temporal_extent = _generate_sample_temporal_extent()
        project = schemas.ProjectCreate(
            id=schemas.ProjectId(uuid.uuid4()),
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"sample_{_FAKE_EN.sentence()}",
                pt=f"amostra_{_FAKE_PT.sentence()}",
            ),
            description=schemas.LocalizableDraftDescription(
                en=_FAKE_EN.paragraph(nb_sentences=4),
                pt=_FAKE_PT.paragraph(nb_sentences=4),
            ),
            root_path=f"/{root_path}/{_FAKE_EN.file_path(depth=_FAKE_EN.random_int(0, 3), absolute=False)}",
            bbox_4326=(
                _generate_sample_bbox(
                    float(_FAKE_EN.longitude()), float(_FAKE_EN.latitude())
                )
                if _FAKE_EN.random_digit() >= 1
                else None
            ),
            temporal_extent_begin=temporal_extent[0],
            temporal_extent_end=temporal_extent[1],
            links=links,
        )
        mission_generator = generate_sample_survey_missions(
            owners, project.id, dataset_categories, domain_types, workflow_stages
        )
        missions = [next(mission_generator) for _ in range(_FAKE_EN.random_int(1, 10))]
        yield project, missions


def generate_sample_survey_missions(
    owners: Sequence[schemas.UserId],
    project_id: schemas.ProjectId,
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
) -> Iterator[
    tuple[schemas.SurveyMissionCreate, list[schemas.SurveyRelatedRecordCreate]],
]:
    for _ in count():
        links = (
            [next(generate_sample_link()) for _ in range(_FAKE_EN.random_int(0, 15))]
            if _FAKE_EN.random_digit() < 5
            else []
        )
        temporal_extent = _generate_sample_temporal_extent()
        mission = schemas.SurveyMissionCreate(
            id=schemas.SurveyMissionId(uuid.uuid4()),
            project_id=project_id,
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"sample_{_FAKE_EN.sentence()}",
                pt=f"amostra_{_FAKE_PT.sentence()}",
            ),
            description=schemas.LocalizableDraftDescription(
                en=_FAKE_EN.paragraph(nb_sentences=4),
                pt=_FAKE_PT.paragraph(nb_sentences=4),
            ),
            relative_path=_FAKE_EN.file_path(
                depth=_FAKE_EN.random_int(1, 8), absolute=False
            ),
            bbox_4326=(
                _generate_sample_bbox(
                    float(_FAKE_EN.longitude()), float(_FAKE_EN.latitude())
                )
                if _FAKE_EN.random_digit() >= 1
                else None
            ),
            temporal_extent_begin=temporal_extent[0],
            temporal_extent_end=temporal_extent[1],
            links=links,
        )
        record_generator = generate_sample_survey_related_records(
            owners, mission.id, dataset_categories, domain_types, workflow_stages
        )
        records = [next(record_generator) for _ in range(_FAKE_EN.random_int(1, 100))]
        yield mission, records


def generate_sample_survey_related_records(
    owners: Sequence[schemas.UserId],
    survey_mission_id: schemas.SurveyMissionId,
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
) -> Iterator[schemas.SurveyRelatedRecordCreate]:
    temporal_extent = _generate_sample_temporal_extent()
    for _ in count():
        links = (
            [next(generate_sample_link()) for _ in range(_FAKE_EN.random_int(0, 15))]
            if _FAKE_EN.random_digit() < 5
            else []
        )
        assets = (
            [next(generate_sample_asset()) for _ in range(_FAKE_EN.random_int(0, 12))]
            if _FAKE_EN.random_digit() < 5
            else []
        )
        yield schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(uuid.uuid4()),
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"sample_{_FAKE_EN.sentence()}",
                pt=f"amostra_{_FAKE_PT.sentence()}",
            ),
            description=schemas.LocalizableDraftDescription(
                en=_FAKE_EN.paragraph(nb_sentences=4),
                pt=_FAKE_PT.paragraph(nb_sentences=4),
            ),
            survey_mission_id=survey_mission_id,
            dataset_category_id=random.choice(dataset_categories),
            domain_type_id=random.choice(domain_types),
            workflow_stage_id=random.choice(workflow_stages),
            relative_path=_FAKE_EN.file_path(
                depth=_FAKE_EN.random_int(1, 8), absolute=False
            ),
            bbox_4326=(
                _generate_sample_bbox(
                    float(_FAKE_EN.longitude()), float(_FAKE_EN.latitude())
                )
                if _FAKE_EN.random_digit() >= 1
                else None
            ),
            temporal_extent_begin=temporal_extent[0],
            temporal_extent_end=temporal_extent[1],
            links=links,
            assets=assets,
        )


def generate_sample_asset() -> Iterator[schemas.RecordAssetCreate]:
    for _ in count():
        links = (
            [next(generate_sample_link()) for _ in range(_FAKE_EN.random_int(0, 15))]
            if _FAKE_EN.random_digit() < 5
            else []
        )
        yield schemas.RecordAssetCreate(
            id=schemas.RecordAssetId(uuid.uuid4()),
            name=schemas.LocalizableDraftName(
                en=f"sample_{_FAKE_EN.sentence()}",
                pt=f"amostra_{_FAKE_PT.sentence()}",
            ),
            description=schemas.LocalizableDraftDescription(
                en=_FAKE_EN.paragraph(nb_sentences=4),
                pt=_FAKE_PT.paragraph(nb_sentences=4),
            ),
            relative_path=_FAKE_EN.file_path(
                depth=_FAKE_EN.random_int(1, 4), absolute=False
            ),
            links=links,
        )


def generate_sample_link() -> Iterator[schemas.LinkSchema]:
    for _ in count():
        yield schemas.LinkSchema(
            url=_FAKE_EN.url(),
            media_type=_FAKE_EN.random_element(
                (
                    "application/json",
                    "application/pdf",
                    "application/xml",
                    "text/html",
                    "text/plain",
                )
            ),
            relation=_FAKE_EN.random_element(
                # this is a list of IANA link relations, as gotten from:
                # https://www.iana.org/assignments/link-relations/link-relations.xhtml
                (
                    "about",
                    "acl",
                    "alternate",
                    "amphtml",
                    "api-catalog",
                    "appendix",
                    "apple-touch-icon",
                    "apple-touch-startup-image",
                    "archives",
                    "author",
                    "blocked-by",
                    "bookmark",
                    "c2pa-manifest",
                    "canonical",
                    "chapter",
                    "cite-as",
                    "collection",
                    "compression-dictionary",
                    "contents",
                    "convertedfrom",
                    "copyright",
                    "create-form",
                    "current",
                    "deprecation",
                    "describedby",
                    "describes",
                    "disclosure",
                    "dns-prefetch",
                    "duplicate",
                    "edit",
                    "edit-form",
                    "edit-media",
                    "enclosure",
                    "external",
                    "first",
                    "geofeed",
                    "glossary",
                    "help",
                    "hosts",
                    "hub",
                    "ice-server",
                    "icon",
                    "index",
                    "intervalafter",
                    "intervalbefore",
                    "intervalcontains",
                    "intervaldisjoint",
                    "intervalduring",
                    "intervalequals",
                    "intervalfinishedby",
                    "intervalfinishes",
                    "intervalin",
                    "intervalmeets",
                    "intervalmetby",
                    "intervaloverlappedby",
                    "intervaloverlaps",
                    "intervalstartedby",
                    "intervalstarts",
                    "item",
                    "last",
                    "latest-version",
                    "license",
                    "linkset",
                    "lrdd",
                    "manifest",
                    "mask-icon",
                    "me",
                    "media-feed",
                    "memento",
                    "micropub",
                    "modulepreload",
                    "monitor",
                    "monitor-group",
                    "next",
                    "next-archive",
                    "nofollow",
                    "noopener",
                    "noreferrer",
                    "opener",
                    "openid2.local_id",
                    "openid2.provider",
                    "original",
                    "p3pv1",
                    "payment",
                    "pingback",
                    "preconnect",
                    "predecessor-version",
                    "prefetch",
                    "preload",
                    "prerender",
                    "prev",
                    "preview",
                    "previous",
                    "prev-archive",
                    "privacy-policy",
                    "profile",
                    "publication",
                    "rdap-active",
                    "rdap-bottom",
                    "rdap-down",
                    "rdap-top",
                    "rdap-up",
                    "related",
                    "restconf",
                    "replies",
                    "ruleinput",
                    "search",
                    "section",
                    "self",
                    "service",
                    "service-desc",
                    "service-doc",
                    "service-meta",
                    "sip-trunking-capability",
                    "sponsored",
                    "start",
                    "status",
                    "stylesheet",
                    "subsection",
                    "successor-version",
                    "sunset",
                    "tag",
                    "terms-of-service",
                    "timegate",
                    "timemap",
                    "type",
                    "ugc",
                    "up",
                    "version-history",
                    "via",
                    "webmention",
                    "working-copy",
                    "working-copy-of",
                )
            ),
            link_description=schemas.LocalizableDraftDescription(
                en=_FAKE_EN.paragraph(nb_sentences=3),
                pt=_FAKE_PT.paragraph(nb_sentences=3),
            ),
        )


def _generate_sample_bbox(x: float, y: float) -> str:
    width = random.random() * 0.4  # 0 - .4 degrees
    height = random.random() * 0.4  # 0 - .4 degrees
    other_x = (x + width + 180) % 360 - 180
    other_y = (y + height + 90) % 180 - 90
    x_min = min(x, other_x)
    x_max = max(x, other_x)
    y_min = min(y, other_y)
    y_max = max(y, other_y)
    return shapely.box(x_min, y_min, x_max, y_max).wkt


def _generate_sample_temporal_extent() -> tuple[dt.date | None, dt.date | None]:
    end = _FAKE_EN.date_object()
    start = _FAKE_EN.date_object(end_datetime=dt.datetime(end.year, end.month, end.day))
    return random.choice([start, None]), random.choice([end, None])
