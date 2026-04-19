"""add_stock_logic_scores table

Revision ID: add_stock_logic_scores
Revises: add_stock_logic_exposures
Create Date: 2026-04-19 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_logic_scores'
down_revision: Union[str, None] = 'add_stock_logic_exposures'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_logic_scores table for STOCK-04 logic score calculation."""
    op.create_table(
        'stock_logic_scores',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('total_exposure', sa.Numeric(7, 4), nullable=True),
        sa.Column('contributing_logics', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_stock_logic_scores_code_date')
    )

    # Create indexes for efficient querying
    op.create_index('ix_stock_logic_scores_stock_code', 'stock_logic_scores', ['stock_code'])
    op.create_index('ix_stock_logic_scores_date', 'stock_logic_scores', ['snapshot_date'])


def downgrade() -> None:
    """Drop stock_logic_scores table."""
    op.drop_index('ix_stock_logic_scores_date', table_name='stock_logic_scores')
    op.drop_index('ix_stock_logic_scores_stock_code', table_name='stock_logic_scores')
    op.drop_table('stock_logic_scores')
