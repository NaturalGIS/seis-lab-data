import uuid

from .. import schemas

PROJECTS_TO_CREATE = [
    schemas.ProjectCreate(
        id=uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3"),
        owner="fakeowner1",
        name={"en": "My first project", "pt": "O meu primeiro projeto"},
        description={
            "en": "A fake description for my first project",
            "pt": "Uma descrição sintética para o meu primeiro projeto",
        },
        root_path="/projects/first",
        links=[
            {
                "url": "https://fakeurl.com",
                "media_type": "text/html",
                "relation": "related",
                "description": {
                    "en": "A fake description for link",
                    "pt": "Uma descrição falsa para o link",
                },
            }
        ],
    ),
    schemas.ProjectCreate(
        id=uuid.UUID("9a877fbe-da98-45ab-af70-711879c6fc01"),
        owner="fakeowner1",
        name={"en": "My second project", "pt": "O meu segundo projeto"},
        description={
            "en": "A fake description for my second project",
            "pt": "Uma descrição sintética para o meu segundo projeto",
        },
        root_path="/projects/second",
        links=[
            {
                "url": "https://fakeurl.com",
                "media_type": "text/html",
                "relation": "related",
                "description": {
                    "en": "A fake description for link",
                    "pt": "Uma descrição falsa para o link",
                },
            }
        ],
    ),
]
