import uuid

from .. import schemas

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

PROJECTS_TO_CREATE = [
    schemas.ProjectCreate(
        id=_my_first_project_id,
        owner=_owner_id,
        name={"en": "My first project", "pt": "O meu primeiro projeto"},
        description={
            "en": "A fake description for my first project",
            "pt": "Uma descrição sintética para o meu primeiro projeto",
        },
        root_path="/projects/first",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for link",
                    "pt": "Uma descrição falsa para o link",
                },
            ),
        ],
    ),
    schemas.ProjectCreate(
        id=_my_second_project_id,
        owner=_owner_id,
        name={"en": "My second project", "pt": "O meu segundo projeto"},
        description={
            "en": "A fake description for my second project",
            "pt": "Uma descrição sintética para o meu segundo projeto",
        },
        root_path="/projects/second",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for link",
                    "pt": "Uma descrição falsa para o link",
                },
            )
        ],
    ),
]

SURVEY_MISSIONS_TO_CREATE = [
    schemas.SurveyMissionCreate(
        id=_my_first_survey_mission_id,
        owner=_owner_id,
        project_id=_my_first_project_id,
        name={"en": "My first survey mission", "pt": "A minha primeira missão"},
        description={
            "en": "This is the description for my first survey mission",
            "pt": "Esta é a descrição para a minha primeira missão",
        },
        relative_path="mission1",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl1.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for the first link",
                    "pt": "Uma descrição falsa para o primeiro link",
                },
            ),
            schemas.LinkSchema(
                url="https://fakeurl2.com",
                media_type="text/html",
                relation="also-related",
                description={
                    "en": "A fake description for the second link",
                    "pt": "Uma descrição falsa para o segundo link",
                },
            ),
        ],
    ),
    schemas.SurveyMissionCreate(
        id=_my_second_survey_mission_id,
        owner=_owner_id,
        project_id=_my_first_project_id,
        name={"en": "My second survey mission", "pt": "A minha segunda missão"},
        description={
            "en": "This is the description for my second survey mission",
            "pt": "Esta é a descrição para a minha segunda missão",
        },
        relative_path="mission2",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl1.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for the first link",
                    "pt": "Uma descrição falsa para o primeiro link",
                },
            ),
            schemas.LinkSchema(
                url="https://fakeurl2.com",
                media_type="text/html",
                relation="also-related",
                description={
                    "en": "A fake description for the second link",
                    "pt": "Uma descrição falsa para o segundo link",
                },
            ),
        ],
    ),
    schemas.SurveyMissionCreate(
        id=_my_third_survey_mission_id,
        owner=_owner_id,
        project_id=_my_first_project_id,
        name={"en": "My third survey mission", "pt": "A minha terceira missão"},
        description={
            "en": "This is the description for my third survey mission",
            "pt": "Esta é a descrição para a minha terceira missão",
        },
        relative_path="mission3",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl1.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for the first link",
                    "pt": "Uma descrição falsa para o primeiro link",
                },
            ),
            schemas.LinkSchema(
                url="https://fakeurl2.com",
                media_type="text/html",
                relation="also-related",
                description={
                    "en": "A fake description for the second link",
                    "pt": "Uma descrição falsa para o segundo link",
                },
            ),
        ],
    ),
    schemas.SurveyMissionCreate(
        id=_my_fourth_survey_mission_id,
        owner=_owner_id,
        project_id=_my_second_project_id,
        name={"en": "My fourth survey mission", "pt": "A minha quarta missão"},
        description={
            "en": "This is the description for my fourth survey mission",
            "pt": "Esta é a descrição para a minha quarta missão",
        },
        relative_path="mission4",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl1.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for the first link",
                    "pt": "Uma descrição falsa para o primeiro link",
                },
            ),
            schemas.LinkSchema(
                url="https://fakeurl2.com",
                media_type="text/html",
                relation="also-related",
                description={
                    "en": "A fake description for the second link",
                    "pt": "Uma descrição falsa para o segundo link",
                },
            ),
        ],
    ),
    schemas.SurveyMissionCreate(
        id=_my_fifth_survey_mission_id,
        owner=_owner_id,
        project_id=_my_second_project_id,
        name={"en": "My fifth survey mission", "pt": "A minha quinta missão"},
        description={
            "en": "This is the description for my fifth survey mission",
            "pt": "Esta é a descrição para a minha quinta missão",
        },
        relative_path="mission5",
        links=[
            schemas.LinkSchema(
                url="https://fakeurl1.com",
                media_type="text/html",
                relation="related",
                description={
                    "en": "A fake description for the first link",
                    "pt": "Uma descrição falsa para o primeiro link",
                },
            ),
            schemas.LinkSchema(
                url="https://fakeurl2.com",
                media_type="text/html",
                relation="also-related",
                description={
                    "en": "A fake description for the second link",
                    "pt": "Uma descrição falsa para o segundo link",
                },
            ),
        ],
    ),
]
