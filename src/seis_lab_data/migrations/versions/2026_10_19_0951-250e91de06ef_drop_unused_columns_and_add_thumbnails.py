"""drop unused columns and add thumbnails

Revision ID: 250e91de06ef
Revises: 421a23b83456
Create Date: 2026-10-19 09:51:02.279559

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "250e91de06ef"
down_revision: Union[str, Sequence[str], None] = "421a23b83456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("project", sa.Column("thumbnail", sa.LargeBinary(), nullable=True))
    op.drop_index("ix_project_owner_id", table_name="project")
    op.drop_constraint("fk_project_owner_id_appuser", "project", type_="foreignkey")
    op.drop_column("project", "is_valid")
    op.drop_column("project", "discovery_configuration")
    op.drop_column("project", "owner_id")
    op.execute("DROP INDEX idx_recordasset_geog_geometry")
    op.drop_geospatial_index(
        "idx_recordasset_geog",
        table_name="recordasset",
        postgresql_using="gist",
        column_name="geog",
    )
    op.drop_column("recordasset", "is_valid")
    op.drop_geospatial_column("recordasset", "geog")
    op.add_column(
        "surveymission", sa.Column("thumbnail", sa.LargeBinary(), nullable=True)
    )
    op.drop_index("ix_surveymission_owner_id", table_name="surveymission")
    op.drop_constraint(
        "fk_surveymission_owner_id_appuser", "surveymission", type_="foreignkey"
    )
    op.drop_column("surveymission", "is_valid")
    op.drop_column("surveymission", "owner_id")
    op.drop_index("ix_surveyrelatedrecord_owner_id", table_name="surveyrelatedrecord")
    op.drop_constraint(
        "fk_surveyrelatedrecord_owner_id_appuser",
        "surveyrelatedrecord",
        type_="foreignkey",
    )
    op.drop_column("surveyrelatedrecord", "is_valid")
    op.drop_column("surveyrelatedrecord", "owner_id")


def downgrade() -> None:
    """Downgrade schema."""
    # the dropped values are not recoverable: owner_id comes back nullable
    # (it was NOT NULL) and is_valid comes back false on every row
    op.add_column(
        "surveyrelatedrecord",
        sa.Column("owner_id", sa.VARCHAR(length=100), nullable=True),
    )
    op.add_column(
        "surveyrelatedrecord",
        sa.Column(
            "is_valid",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_surveyrelatedrecord_owner_id_appuser",
        "surveyrelatedrecord",
        "appuser",
        ["owner_id"],
        ["id"],
    )
    op.create_index(
        "ix_surveyrelatedrecord_owner_id",
        "surveyrelatedrecord",
        ["owner_id"],
        unique=False,
    )
    op.add_column(
        "surveymission",
        sa.Column("owner_id", sa.VARCHAR(length=100), nullable=True),
    )
    op.add_column(
        "surveymission",
        sa.Column(
            "is_valid",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_surveymission_owner_id_appuser",
        "surveymission",
        "appuser",
        ["owner_id"],
        ["id"],
    )
    op.create_index(
        "ix_surveymission_owner_id", "surveymission", ["owner_id"], unique=False
    )
    op.drop_column("surveymission", "thumbnail")
    op.add_geospatial_column(
        "recordasset",
        sa.Column(
            "geog",
            Geography(
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "recordasset",
        sa.Column(
            "is_valid",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_geospatial_index(
        "idx_recordasset_geog",
        "recordasset",
        ["geog"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    # martin table sources query via a geometry cast, which the geography GiST
    # index cannot serve
    op.execute(
        "CREATE INDEX idx_recordasset_geog_geometry ON recordasset USING gist ((geog::geometry))"
    )
    op.add_column(
        "project",
        sa.Column("owner_id", sa.VARCHAR(length=100), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column(
            "discovery_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "project",
        sa.Column(
            "is_valid",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_project_owner_id_appuser", "project", "appuser", ["owner_id"], ["id"]
    )
    op.create_index("ix_project_owner_id", "project", ["owner_id"], unique=False)
    op.drop_column("project", "thumbnail")
