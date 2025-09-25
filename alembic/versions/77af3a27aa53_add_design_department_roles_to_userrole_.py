"""Add design department roles to userrole enum

Revision ID: 77af3a27aa53
Revises: 0035cdbb7765
Create Date: 2025-09-25 11:29:28.179098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77af3a27aa53'
down_revision: Union[str, Sequence[str], None] = '0035cdbb7765'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE userrole ADD VALUE 'Design Manager'")
    op.execute("ALTER TYPE userrole ADD VALUE 'Design Team Member'")
    op.execute("ALTER TYPE userrole ADD VALUE 'Document Controller'")
    op.execute("ALTER TYPE userrole ADD VALUE 'Technical Engineer'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
