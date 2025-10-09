"""No-op: schema already created in prior revisions

Revision ID: a609e60bb0a7
Revises: f52a72dfe03a
Create Date: 2025-10-08 11:45:01.143976
"""
from typing import Sequence, Union

revision: str = 'a609e60bb0a7'
down_revision: Union[str, Sequence[str], None] = 'f52a72dfe03a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # No changes; prior migrations covered schema
    pass

def downgrade() -> None:
    # No changes to revert
    pass
