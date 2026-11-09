"""add generate previews to asset discovery configuration

Revision ID: bba69a38f980
Revises: 56be2528f706
Create Date: 2026-11-06 17:49:22.275136

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa

# revision identifiers, used by Alembic.
revision: str = "bba69a38f980"
down_revision: Union[str, Sequence[str], None] = "56be2528f706"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "assetdiscoveryconfiguration",
        sa.Column(
            "generate_previews", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "surveyrelatedrecord",
        sa.Column("asset_discovery_configuration_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_surveyrelatedrecord_asset_discovery_configuration_id",
        "surveyrelatedrecord",
        ["asset_discovery_configuration_id"],
        unique=False,
    )
    op.create_foreign_key(
        "surveyrelatedrecord_asset_discovery_configuration_id_fkey",
        "surveyrelatedrecord",
        "assetdiscoveryconfiguration",
        ["asset_discovery_configuration_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # the seeded configurations whose directories the former
    # config/preview-directories.json listed
    op.execute(
        """
        UPDATE assetdiscoveryconfiguration SET generate_previews = true
        WHERE id IN (
          '107e1150-ab83-48b9-abbf-78db43a52174',
          '7537692e-3247-4a8e-aa6e-ce7ff1edeb94',
          'acd1b6f9-c195-468d-8bb9-4c4d96ab8e42',
          '9030c20e-ac13-4c60-963b-d10dd91429d8',
          'd7cbd359-59ff-42ab-84f6-e8dd56170f5a',
          '4edc6f4f-9465-43cb-a1e1-2ce491920bbd',
          'c1754332-28b1-45b9-9b93-45219fb888dd',
          '0d7e0279-5654-4c1f-bbae-648e8c09dae6',
          '4a3c7c46-6b79-4a1c-8481-f4cb406b7640',
          'bac1c5f2-e389-447f-ab3a-5137dd7a375a',
          '789815f8-6eb1-4b0e-b86d-9adf4409d164',
          '07253aa3-b9f0-40b7-8319-89e984891036',
          'b8eee2f2-c0d0-4e38-bc6e-00d3ea585b5e',
          '1db8a6a4-dbaf-4545-8260-12e5f7905d75',
          'a50049c2-aaa9-480e-8dcc-257be3ae71df',
          'ffe5e89b-09de-4f1f-8203-c3a799fb6a46',
          '451c368b-b48b-4b04-a0d8-7f3cf4ec277d',
          '66dfbd30-3531-4613-ae77-69025744b1f7',
          '7ee50b66-8b45-4e7b-a246-d249f5db53cb',
          'd0be839d-b1ea-4e34-8753-84e07da6d90d',
          '013dfd89-12e8-4e59-9106-07a22bd2e50f',
          'ba980e5e-64ce-4270-b6c1-41e52d86dbc1',
          '104b4ded-08a9-4650-8212-f4d952ee42c9',
          '112e1a9d-0e60-4db8-a38c-f568209a435c',
          '01b7ac3e-cf75-4efc-b138-f034fcff6798',
          '415ccaa3-a49d-4a56-b9d7-3e43cdf724c4',
          '87a3ec1f-9d7a-4306-8edd-a4edf3f51c48',
          'b3c3e336-07b8-44d1-9f63-5847c874ae14',
          '459a0dd0-f1d4-4dc6-b4a8-5d8ffde5b28a',
          '5e397756-8594-4d91-8c05-b1e1a7fc71a5',
          'f3e868f5-5001-4904-af2d-fcf8773e0a02',
          '10c6ea91-3ebc-4262-be51-4b9c81f9c3c9',
          'c507ef4d-557a-4b66-af42-7d1ff5771ac1',
          '4bbd12a4-e349-4f05-947a-d3b41950a78f',
          '4d40547d-5209-468b-8aa0-ecacfd806bd1',
          'd9ab8030-20f9-4a03-85e1-6831e721c000',
          '8b0067b0-b871-419c-a2eb-cad17b22e5de',
          'a21590d3-a5c3-43c8-8e0c-afca1c3d7612',
          '0af59908-0f05-410c-99d1-f1274f23affb',
          '6d827f3d-0d9b-4b29-a324-0d5a63cf9466',
          '640118b9-b545-49d4-9785-0c8cd886e241',
          '7b8cdb69-1cfa-4b86-ac42-5a4165a1306e',
          '5a05d6e1-74dd-4ec8-a5a4-b841714d21e6',
          '36bae78b-7918-4881-81c6-55172e390687',
          '3d0f23f5-13f9-4143-89fe-1e0e6192bf49',
          '660840f0-ef24-4a4a-877a-54c0f6281f74',
          '8506bec2-822a-4d08-ac23-ab5340798e6c',
          '799f4ae2-825a-4164-bf85-42d9246899ec',
          '7d73ee55-47ca-4458-82fd-7d701a4ff7cd',
          '8a7e35c2-d1e0-4990-8891-c12a6e965b40',
          '701fa403-293a-4537-9e34-bef22ceadd22',
          '861454aa-728f-4110-913e-6ab8abc33bcb',
          '25658033-61b2-4b2c-8120-0b7093e010af',
          '733a9f63-5f8b-4641-9cc9-8c07b8cb87f2',
          '1ba8555f-66bc-4a74-859b-aeb8701ba065',
          '2c5313a3-b0d5-4aab-aa4a-20629ee70b6d',
          '9835a7ba-91d5-45c5-aaa6-c8ad67c2ee97',
          '2ae1d3e1-1b3c-4bb1-989b-4bb513e92427',
          'a081cb9d-4ad3-43f8-a817-d6a590ffb4ca',
          '0dcec126-9549-4b3f-99fb-96e9c7d74dd5',
          '1c9cf956-ab27-41c6-bb7f-84230d6a4353',
          '07c2ccc1-f47c-4ad2-86e4-c3f9783a35d2',
          '9bd691bd-5064-4bfe-85a4-b34b38245723',
          '19fb6932-c693-4a77-9fdb-c69d6b4b10da',
          '776fb586-8535-49d3-a604-082b8a4f8542',
          'c6b48cda-29e9-484a-b3f5-d29ae8012626',
          '203aace8-8dfe-46ad-b277-9a9c9eb562ce',
          '8a178443-57df-47fc-9893-354ac92f1cdf',
          'b67ffcc6-01cc-41c2-8b67-b966b2945fe7',
          'be64e4fd-f616-4dce-b52c-8578bbeb880e',
          '31940e3b-0d99-445d-9aa1-64e87a1fcd4a',
          '4b8ccde5-91b2-4275-b3ba-e1a0971a3293',
          'c0c216f6-838e-4bce-a6b0-4f37161d2c41',
          '02334f48-bdf2-4b1d-8746-5ac26972eb7e',
          'c5cf254d-2c72-4fad-bd11-5e1fb11bddcf',
          '5befdf74-036f-41ca-9148-041cb899a883',
          '0589844d-b6b4-41c4-a914-6659025c0cc4',
          'aa857f8b-1fee-48ea-bad4-5a644323757c',
          'd0e800ce-06dd-4c06-85b3-b484b24342a1',
          '0f3d35a9-44a9-40a5-9d84-09c55fad775d',
          'e0ed2617-1590-4e55-bca9-f24ff3fdcc99',
          '21f73024-10d6-4cb5-8d18-28e783f788f5',
          'dcf18fa2-627c-4243-9d4f-fb3c590cf5fa',
          '8dd25d0f-6b22-4eed-b23c-c0d89babe9e7',
          '95c9b9b0-2f0e-4f1b-a1d6-b2c9f77d4a22',
          '712c2691-b00c-48a8-8a43-565921d405fe',
          'df7fea1b-096b-4614-b440-e3eead88cab4',
          '5d991c02-a3bc-45fc-9a5d-4779d8ce433a',
          'b5dd3874-97ca-40aa-a35c-5861340ebe40',
          '156b46d3-9dfe-42b8-9b25-54027ed43bbe',
          '1488f65c-c2e4-4242-b52c-88db9bd002d3',
          '6b2a3c87-6523-488c-910d-ee759eddd07b',
          '238ffd2e-75b1-411e-b705-3e132d92970c',
          'fe756435-8064-47f1-9a7b-8f0b314bafa3',
          'ee0c7903-590b-40f5-bac9-8328fd3280cf',
          'cb75a5c2-8bfb-48a7-a60b-6b9f9a347f78',
          'adfe3c6a-3a4d-4ebb-80da-e86180da3c76',
          'e38cc926-5cf5-4c34-bc3a-0264fa57f1e9',
          '73f17021-c6ee-45ed-97fb-eefd4eb3acd2',
          'ed5705c4-3f5b-4aaf-9323-98cd7996affe',
          '8ec00765-4e02-475e-9b5d-63ddb0902508',
          '7e3d4af9-02a0-40b0-b5db-c43801b3b170',
          'a3eccc8a-bf48-4754-8a22-43f48fbf3f89',
          'af6defb3-bafe-45f2-a775-27d60e3d5825',
          'd8c140bc-a772-4b0d-9cbb-f9e69ba48682',
          'ebcc3601-35ff-4668-a17f-91cb429eabfb',
          '74b9f427-1b1e-4906-b4bf-c35abaf198c9',
          'ee692900-8da3-4705-b209-d74fa407b8b6',
          '669c8072-025e-4a9c-8717-28e1cbd5a3f8',
          '9ba6943e-bfa9-4407-9c9f-c54a8a39af73',
          'cf2cc908-afac-480e-954a-ed3730c80270',
          '968a4ebc-8eb8-48e4-9fca-90f266773bd0',
          'dd93f99c-ffe8-4ad8-9ea1-1e401c395f14',
          'c452cc0a-018b-4079-9df1-4855fe07a0b2',
          '368ca705-3e0f-4515-8784-7eb0469cfd2c',
          '28b8d312-8302-4cd5-9845-e87c1b69da80',
          'feccc17f-bc8d-4ab3-89a6-8fbade066f43',
          '4bd88cef-1f90-451f-8fd6-18a671a80450',
          'ae50f5c3-7f61-4af1-b45a-1a01f04ff4c1',
          '0b16876d-2631-4c81-8a67-f33ce3ae1c6b',
          '7542cfd4-4f94-4463-8f04-33a2191ba8e7',
          '54f0d7f7-e056-4f10-aaad-e0c431476d6f',
          'dfe884c2-3d77-4177-bf15-8a9d3f17c7f2',
          '5233c3b2-8b93-44b4-9730-e95f08f87f17'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "surveyrelatedrecord_asset_discovery_configuration_id_fkey",
        "surveyrelatedrecord",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_surveyrelatedrecord_asset_discovery_configuration_id",
        table_name="surveyrelatedrecord",
    )
    op.drop_column("surveyrelatedrecord", "asset_discovery_configuration_id")
    op.drop_column("assetdiscoveryconfiguration", "generate_previews")
