"""Add new stages to v3 enum (rename old short labels, add missing long labels)

Revision ID: e82efea2f69b
Revises: df44454d7896
Create Date: 2025-10-10 10:53:14.014220
"""
from typing import Sequence, Union
from alembic import op

revision: str = "e82efea2f69b"
down_revision: Union[str, Sequence[str], None] = "df44454d7896"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _rename_value(old: str, new: str) -> None:
    # If old exists and new doesn't, rename old -> new
    op.execute(f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = 'stagename' AND e.enumlabel = '{old}'
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = 'stagename' AND e.enumlabel = '{new}'
        )
        THEN
            ALTER TYPE stagename RENAME VALUE '{old}' TO '{new}';
        END IF;
    END $$;
    """)

def _add_value(label: str) -> None:
    # If label doesn't exist, add it
    op.execute(f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = 'stagename' AND e.enumlabel = '{label}'
        )
        THEN
            ALTER TYPE stagename ADD VALUE '{label}';
        END IF;
    END $$;
    """)

def upgrade() -> None:
    # Rename existing short labels to long, human-readable ones (if present)
    _rename_value('FINANCE_CONFIRMATION', 'Stage 0 - Finance Confirmation')
    _rename_value('DEAL_CREATION', 'Stage 1 - Deal Creation')
    _rename_value('SITE_VISIT', 'Stage 2A - Design Activation & Site Visit')
    _rename_value('MEASUREMENT', 'Stage 2B - Measurement Requisition')
    _rename_value('INITIAL_DESIGN', 'Stage 3 - Initial Design Development')
    _rename_value('QS_HANDOVER', 'Stage 4 - Forward to QS')
    _rename_value('TECH_REVIEW', 'Stage 5 - Technical Review & Coordination')
    _rename_value('AUTHORITY_PACKAGE', 'Stage 6 - Authority Drawing Package')
    _rename_value('FINAL_DELIVERY', 'Stage 7 - Final Package Delivery')
    _rename_value('EXECUTION_HANDOVER', 'Stage 8 - Handover to Execution')

    # If any of the long labels weren’t present at all, add them
    _add_value('Stage 5 - Technical Review & Coordination')
    _add_value('Stage 6 - Authority Drawing Package')
    _add_value('Stage 7 - Final Package Delivery')
    _add_value('Stage 8 - Handover to Execution')

    # Note: leaving any legacy values (e.g., MANAGEMENT_OVERSIGHT) in the type is harmless.


def downgrade() -> None:
    # Postgres can’t drop enum labels safely; no-op downgrade.
    pass
