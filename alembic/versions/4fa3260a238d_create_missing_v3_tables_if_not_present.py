"""Create missing V3 tables if not present

Revision ID: 4fa3260a238d
Revises: fe431b5f765f
Create Date: 2025-10-08 13:48:29.585676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4fa3260a238d'
down_revision: Union[str, Sequence[str], None] = 'fe431b5f765f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reuse existing named enums; do NOT auto-create during table DDL
stagename = postgresql.ENUM(
    'FINANCE_CONFIRMATION','DEAL_CREATION','SITE_VISIT','MEASUREMENT',
    'INITIAL_DESIGN','QS_HANDOVER','MANAGEMENT_OVERSIGHT',
    'TECH_REVIEW','AUTHORITY_PACKAGE','FINAL_DELIVERY','EXECUTION_HANDOVER',
    name='stagename',
    create_type=False
)
stagev3status = postgresql.ENUM(
    'LOCKED','IN_PROGRESS','COMPLETED',
    name='stagev3status',
    create_type=False
)

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Ensure enums exist (safe on reruns)
    stagename.create(bind, checkfirst=True)
    stagev3status.create(bind, checkfirst=True)

    # Create design_projects_v3 if missing
    if 'design_projects_v3' not in insp.get_table_names():
        op.create_table(
            'design_projects_v3',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('client', sa.String()),
            sa.Column('status', sa.String(), server_default='Active'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deals.id'), unique=True),
        )

    # Create design_stages_v3 if missing
    if 'design_stages_v3' not in insp.get_table_names():
        op.create_table(
            'design_stages_v3',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', stagename, nullable=False),
            sa.Column('status', stagev3status, nullable=False),
            sa.Column('order', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('design_projects_v3.id'), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if 'design_stages_v3' in insp.get_table_names():
        op.drop_table('design_stages_v3')
    if 'design_projects_v3' in insp.get_table_names():
        op.drop_table('design_projects_v3')

    # Drop enums only if nothing else uses them
    stagev3status.drop(bind, checkfirst=True)
    stagename.drop(bind, checkfirst=True)