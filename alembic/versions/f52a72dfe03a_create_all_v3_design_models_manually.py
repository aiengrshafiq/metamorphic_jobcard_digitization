"""Create deals table and ensure enums exist (idempotent)

Revision ID: f52a72dfe03a
Revises: a8116ad7e803
Create Date: 2025-10-08 11:11:12.953670
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f52a72dfe03a'
down_revision: Union[str, Sequence[str], None] = 'a8116ad7e803'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuse named enums; don't auto-create during table DDL
commitmentpackage = postgresql.ENUM(
    'DESIGN_BUILD', 'GUESSTIMATE', 'DESIGN_ONLY', 'GOLD_VR',
    name='commitmentpackage',
    create_type=False
)
stagename = postgresql.ENUM(
    'FINANCE_CONFIRMATION', 'DEAL_CREATION', 'SITE_VISIT', 'MEASUREMENT',
    'INITIAL_DESIGN', 'QS_HANDOVER', 'MANAGEMENT_OVERSIGHT',
    'TECH_REVIEW', 'AUTHORITY_PACKAGE', 'FINAL_DELIVERY', 'EXECUTION_HANDOVER',
    name='stagename',
    create_type=False
)
stagev3status = postgresql.ENUM(
    'LOCKED', 'IN_PROGRESS', 'COMPLETED',
    name='stagev3status',
    create_type=False
)

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Ensure all enums exist (safe to re-run)
    commitmentpackage.create(bind, checkfirst=True)
    stagename.create(bind, checkfirst=True)
    stagev3status.create(bind, checkfirst=True)

    # a8116ad7e803 already created design_projects_v3 and design_stages_v3.
    # This migration ONLY creates 'deals'.
    if 'deals' not in insp.get_table_names():
        op.create_table(
            'deals',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('project_name', sa.String(), nullable=False),
            sa.Column('client_name', sa.String(), nullable=False),
            sa.Column('client_contact', sa.String()),
            sa.Column('location', sa.String()),
            sa.Column('contract_type', commitmentpackage, nullable=False),
            sa.Column('budget', sa.Numeric(12, 2)),
            sa.Column('payment_date', sa.Date()),
            sa.Column('contract_date', sa.Date()),
            sa.Column('initial_brief_link', sa.Text()),
            sa.Column('floor_plan_link', sa.Text()),
            sa.Column('as_built_link', sa.Text()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
            sa.Column('sip_id', sa.Integer(), sa.ForeignKey('users.id')),
        )

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if 'deals' in insp.get_table_names():
        op.drop_table('deals')

    # Drop enums only if nothing else uses them; checkfirst avoids errors
    stagev3status.drop(bind, checkfirst=True)
    stagename.drop(bind, checkfirst=True)
    commitmentpackage.drop(bind, checkfirst=True)
