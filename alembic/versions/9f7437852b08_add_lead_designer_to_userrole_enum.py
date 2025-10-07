"""Add lead designer to userrole enum

Revision ID: 9f7437852b08
Revises: a63206b036a1
Create Date: 2025-10-06 14:58:27.595155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f7437852b08'
down_revision: Union[str, Sequence[str], None] = 'a63206b036a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE userrole ADD VALUE 'Lead Designer'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
