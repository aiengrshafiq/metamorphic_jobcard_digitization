"""Add finance, lead designer, sip roles

Revision ID: a0754ca56759
Revises: 2122175e6966
Create Date: 2025-10-07 14:47:27.922214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0754ca56759'
down_revision: Union[str, Sequence[str], None] = '2122175e6966'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE userrole ADD VALUE 'Sales In-Charge Person'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
