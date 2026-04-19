"""add_stock_composite_scores table

Revision ID: add_stock_composite_scores
Revises: add_stock_logic_scores
Create Date: 2026-04-19 220000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_composite_scores'
down_revision: Union[str, None] = 'add_sector_keywords'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_composite_scores table for STOCK-08 composite score calculation."""
    op.create_table(
        'stock_composite_scores',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('market_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('composite_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('recommendation_rank', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_stock_composite_scores_code_date')
    )

    # Create indexes for efficient querying
    op.create_index('ix_stock_composite_scores_stock_code', 'stock_composite_scores', ['stock_code'])
    op.create_index('ix_stock_composite_scores_date', 'stock_composite_scores', ['snapshot_date'])
    op.create_index('ix_stock_composite_scores_rank', 'stock_composite_scores', ['recommendation_rank'])


def downgrade() -> None:
    """Drop stock_composite_scores table."""
    op.drop_index('ix_stock_composite_scores_rank', table_name='stock_composite_scores')
    op.drop_index('ix_stock_composite_scores_date', table_name='stock_composite_scores')
    op.drop_index('ix_stock_composite_scores_stock_code', table_name='stock_composite_scores')
    op.drop_table('stock_composite_scores')
