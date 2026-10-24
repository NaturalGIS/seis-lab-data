"""simplify localizable fields to plain strings

Revision ID: 56be2528f706
Revises: 250e91de06ef
Create Date: 2026-10-24 16:46:13.297386

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "56be2528f706"
down_revision: Union[str, Sequence[str], None] = "250e91de06ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, max length) of the columns that change from a JSONB
# `{"en": ..., "pt": ...}` dict into a plain string
_LOCALIZED_COLUMNS = (
    ("datasetcategory", "name", 100),
    ("workflowstage", "name", 100),
    ("project", "name", 100),
    ("project", "description", 500),
    ("surveymission", "name", 100),
    ("surveymission", "description", 500),
    ("surveyrelatedrecord", "name", 100),
    ("surveyrelatedrecord", "description", 500),
    ("recordasset", "name", 100),
    ("recordasset", "description", 500),
    ("surveyrelatedrecordselflink", "relation", 50),
)

_TABLES_WITH_NAME_GIN_INDEX = (
    "project",
    "surveymission",
    "surveyrelatedrecord",
    "recordasset",
)

_TABLES_WITH_LINKS = (
    "project",
    "surveymission",
    "surveyrelatedrecord",
    "recordasset",
)


def upgrade() -> None:
    """Upgrade schema."""
    # GIN indexes cannot be rebuilt on a varchar column, so they must go before
    # the column types are changed
    for table in _TABLES_WITH_NAME_GIN_INDEX:
        op.drop_index(
            op.f(f"idx_{table}_name_gin"), table_name=table, postgresql_using="gin"
        )

    # keep the english value, falling back to the portuguese one
    for table, column, length in _LOCALIZED_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sqlmodel.sql.sqltypes.AutoString(length=length),
            nullable=False,
            postgresql_using=(
                f"left(coalesce(nullif({column}->>'en', ''), {column}->>'pt', ''), {length})"
            ),
        )

    # links stay as JSONB, but their `link_description` becomes a plain string
    for table in _TABLES_WITH_LINKS:
        op.execute(f"""
            UPDATE {table}
            SET links = (
                SELECT coalesce(
                    jsonb_agg(
                        CASE WHEN jsonb_typeof(link->'link_description') = 'object'
                            THEN jsonb_set(
                                link,
                                '{{link_description}}',
                                to_jsonb(coalesce(
                                    nullif(link->'link_description'->>'en', ''),
                                    link->'link_description'->>'pt',
                                    ''
                                ))
                            )
                            ELSE link
                        END
                        ORDER BY position
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(links) WITH ORDINALITY AS t(link, position)
            )
            WHERE jsonb_typeof(links) = 'array'
        """)


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES_WITH_LINKS:
        op.execute(f"""
            UPDATE {table}
            SET links = (
                SELECT coalesce(
                    jsonb_agg(
                        CASE WHEN jsonb_typeof(link->'link_description') = 'string'
                            THEN jsonb_set(
                                link,
                                '{{link_description}}',
                                jsonb_build_object('en', link->>'link_description')
                            )
                            ELSE link
                        END
                        ORDER BY position
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(links) WITH ORDINALITY AS t(link, position)
            )
            WHERE jsonb_typeof(links) = 'array'
        """)

    for table, column, length in _LOCALIZED_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=length),
            type_=postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            postgresql_using=f"jsonb_build_object('en', {column})",
        )

    for table in _TABLES_WITH_NAME_GIN_INDEX:
        op.create_index(
            op.f(f"idx_{table}_name_gin"),
            table,
            ["name"],
            unique=False,
            postgresql_using="gin",
        )
