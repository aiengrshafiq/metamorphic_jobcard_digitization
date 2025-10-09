"""Add design_tasks_v3 table (idempotent); do NOT drop legacy tables

Revision ID: 30e7bbdf7110
Revises: 4fa3260a238d
Create Date: 2025-10-08 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "30e7bbdf7110"
down_revision: Union[str, Sequence[str], None] = "4fa3260a238d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Create design_tasks_v3 if missing
    if "design_tasks_v3" not in insp.get_table_names():
        op.create_table(
            "design_tasks_v3",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("status", sa.String(), server_default="Open"),
            sa.Column("due_date", sa.Date()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("file_link", sa.Text()),
            sa.Column("stage_id", sa.Integer(), sa.ForeignKey("design_stages_v3.id"), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "design_tasks_v3" in insp.get_table_names():
        op.drop_table("design_tasks_v3")
