"""add_constraint_checks_table

Revision ID: add_constraint_checks_table
Revises: add_stock_catalysts
Create Date: 2026-04-19 230000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_constraint_checks_table'
down_revision: Union[str, None] = 'add_stock_catalysts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create constraint_checks table for A-share trading constraints (EXEC-02)."""
    op.create_table(
        'constraint_checks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('limit_status', sa.String(20), nullable=True),
        sa.Column('is_suspended', sa.Boolean(), nullable=True),
        sa.Column('chasing_risk_level', sa.String(20), nullable=True),
        sa.Column('applied_constraints', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_constraint_checks_stock_date')
    )

    # Create indexes for efficient querying
    op.create_index('ix_constraint_checks_stock_code', 'constraint_checks', ['stock_code'])
    op.create_index('ix_constraint_checks_date', 'constraint_checks', ['snapshot_date'])


def downgrade() -> None:
    """Drop constraint_checks table."""
    op.drop_index('ix_constraint_checks_date', table_name='constraint_checks')
    op.drop_index('ix_constraint_checks_stock_code', table_name='constraint_checks')
    op.drop_table('constraint_checks')
