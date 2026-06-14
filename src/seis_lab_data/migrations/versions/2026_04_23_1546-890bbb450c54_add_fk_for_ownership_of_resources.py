"""add fk for ownership of resources

Revision ID: 890bbb450c54
Revises: c4061cb6da28
Create Date: 2026-04-23 15:46:45.342159

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa
import sqlmodel  # noqa


# revision identifiers, used by Alembic.
revision: str = "890bbb450c54"
down_revision: Union[str, Sequence[str], None] = "c4061cb6da28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("project", "owner", new_column_name="owner_id")
    op.drop_index(op.f("ix_project_owner"), table_name="project")
    op.create_index(op.f("ix_project_owner_id"), "project", ["owner_id"], unique=False)
    op.create_foreign_key(
        "fk_project_owner_id_appuser", "project", "appuser", ["owner_id"], ["id"]
    )
    op.alter_column("surveymission", "owner", new_column_name="owner_id")
    op.drop_index(op.f("ix_surveymission_owner"), table_name="surveymission")
    op.create_index(
        op.f("ix_surveymission_owner_id"), "surveymission", ["owner_id"], unique=False
    )
    op.create_foreign_key(
        "fk_surveymission_owner_id_appuser",
        "surveymission",
        "appuser",
        ["owner_id"],
        ["id"],
    )
    op.alter_column("surveyrelatedrecord", "owner", new_column_name="owner_id")
    op.drop_index(
        op.f("ix_surveyrelatedrecord_owner"), table_name="surveyrelatedrecord"
    )
    op.create_index(
        op.f("ix_surveyrelatedrecord_owner_id"),
        "surveyrelatedrecord",
        ["owner_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_surveyrelatedrecord_owner_id_appuser",
        "surveyrelatedrecord",
        "appuser",
        ["owner_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_surveyrelatedrecord_owner_id_appuser",
        "surveyrelatedrecord",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_surveyrelatedrecord_owner_id"), table_name="surveyrelatedrecord"
    )
    op.alter_column("surveyrelatedrecord", "owner_id", new_column_name="owner")
    op.create_index(
        op.f("ix_surveyrelatedrecord_owner"),
        "surveyrelatedrecord",
        ["owner"],
        unique=False,
    )
    op.drop_constraint(
        "fk_surveymission_owner_id_appuser", "surveymission", type_="foreignkey"
    )
    op.drop_index(op.f("ix_surveymission_owner_id"), table_name="surveymission")
    op.alter_column("surveymission", "owner_id", new_column_name="owner")
    op.create_index(
        op.f("ix_surveymission_owner"), "surveymission", ["owner"], unique=False
    )
    op.drop_constraint("fk_project_owner_id_appuser", "project", type_="foreignkey")
    op.drop_index(op.f("ix_project_owner_id"), table_name="project")
    op.alter_column("project", "owner_id", new_column_name="owner")
    op.create_index(op.f("ix_project_owner"), "project", ["owner"], unique=False)
