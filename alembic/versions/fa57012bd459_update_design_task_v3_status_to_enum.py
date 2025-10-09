"""Update design task v3 status to enum

Revision ID: fa57012bd459
Revises: 318d64334e06
Create Date: 2025-10-09 12:29:27.636545
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fa57012bd459"
down_revision: Union[str, Sequence[str], None] = "318d64334e06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the enum ONCE and reuse it
taskstatus_enum = postgresql.ENUM(
    "OPEN", "SUBMITTED", "REVISION", "APPROVED",
    name="taskstatusv3",
    create_type=False,  # don't auto-create on column use
)

def upgrade() -> None:
    bind = op.get_bind()

    # 1) Create enum type if missing
    taskstatus_enum.create(bind, checkfirst=True)

    # 2) Normalize existing data to valid enum labels
    #    (handles old values like 'Open', 'Submitted', etc.)
    op.execute("""
        UPDATE design_tasks_v3
        SET status = UPPER(status)
        WHERE status IS NOT NULL
          AND status <> UPPER(status)
    """)

    # Default old rows that are NULL to OPEN (optional; remove if you want to keep NULLs)
    op.execute("""
        UPDATE design_tasks_v3
        SET status = 'OPEN'
        WHERE status IS NULL
    """)

    # 3) Drop previous text default if any, then set enum default
    op.execute("ALTER TABLE design_tasks_v3 ALTER COLUMN status DROP DEFAULT;")

    # 4) Alter column type using USING clause so Postgres can cast
    op.alter_column(
        "design_tasks_v3",
        "status",
        existing_type=sa.VARCHAR(),
        type_=taskstatus_enum,
        existing_nullable=True,
        nullable=False,  # make NOT NULL; change to True if you want nullable
        postgresql_using="status::taskstatusv3",
    )

    # 5) Set new enum default
    op.execute("ALTER TABLE design_tasks_v3 ALTER COLUMN status SET DEFAULT 'OPEN';")


def downgrade() -> None:
    bind = op.get_bind()

    # 1) Drop enum default
    op.execute("ALTER TABLE design_tasks_v3 ALTER COLUMN status DROP DEFAULT;")

    # 2) Cast back to text
    op.alter_column(
        "design_tasks_v3",
        "status",
        existing_type=taskstatus_enum,
        type_=sa.VARCHAR(),
        existing_nullable=False,
        nullable=True,
        postgresql_using="status::text",
    )

    # 3) (Optional) restore old text default
    op.execute("ALTER TABLE design_tasks_v3 ALTER COLUMN status SET DEFAULT 'Open';")

    # 4) Drop the enum type if nothing else uses it
    taskstatus_enum.drop(bind, checkfirst=True)
