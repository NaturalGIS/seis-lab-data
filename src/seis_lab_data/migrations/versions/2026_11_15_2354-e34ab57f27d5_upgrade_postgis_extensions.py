"""upgrade postgis extensions

Revision ID: e34ab57f27d5
Revises: ef97b0c4e356
Create Date: 2026-11-15 23:54:39.192448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa


# revision identifiers, used by Alembic.
revision: str = 'e34ab57f27d5'
down_revision: Union[str, Sequence[str], None] = 'ef97b0c4e356'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # updates the installed PostGIS extensions (postgis, postgis_topology) to the
    # version of the PostGIS libraries of the database image
    op.execute("SELECT postgis_extensions_upgrade()")


def downgrade() -> None:
    """Downgrade schema."""
    # PostGIS does not support downgrading its extensions, they keep the version
    # they were upgraded to
    pass
