"""strip leading slashes from archive paths

Revision ID: efa9962c72ae
Revises: 7ac791ffea8e
Create Date: 2026-11-24 21:53:30.323506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa


# revision identifiers, used by Alembic.
revision: str = 'efa9962c72ae'
down_revision: Union[str, Sequence[str], None] = '7ac791ffea8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # archive paths are relative: an absolute path joined onto the archive root
    # discards the root, along with the mission's directory for asset paths
    for table in ("surveymission", "recordasset"):
        op.execute(
            f"UPDATE {table} SET relative_path = ltrim(relative_path, '/') "
            "WHERE relative_path LIKE '/%'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # the removed slashes are not restored, as they are not needed and their former
    # presence is not recorded
    pass
