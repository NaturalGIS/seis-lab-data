import uuid

from .. import schemas

MARINE_CAMPAIGNS_TO_CREATE = [
    schemas.MarineCampaignCreate(
        id=uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3"),
        owner="fakeowner1",
        name={"en": "My first campaign", "pt": "A minha primeira campanha"},
        description={
            "en": "A fake description for my first campaign",
            "pt": "Uma descrição sintética para a minha primeira campanha",
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
    schemas.MarineCampaignCreate(
        id=uuid.UUID("9a877fbe-da98-45ab-af70-711879c6fc01"),
        owner="fakeowner1",
        name={"en": "My second campaign", "pt": "A minha segunda campanha"},
        description={
            "en": "A fake description for my second campaign",
            "pt": "Uma descrição sintética para a minha segunda campanha",
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
