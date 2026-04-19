"""add_stock_market_scores_table

Revision ID: add_stock_market_scores
Revises: add_stocks_table
Create Date: 2026-04-19 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_market_scores'
down_revision: Union[str, None] = 'add_stocks_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_market_scores table for STOCK-05: Stock Market Radar.

    This table stores daily technical and sentiment scores for individual stocks,
    calculated from pure volume-price data.
    """
    op.create_table(
        'stock_market_scores',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('technical_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('market_composite', sa.Numeric(7, 4), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_stock_market_scores_code_date')
    )

    # Create indexes for efficient querying
    op.create_index('ix_stock_market_scores_stock_code', 'stock_market_scores', ['stock_code'])
    op.create_index('ix_stock_market_scores_date', 'stock_market_scores', ['snapshot_date'])


def downgrade() -> None:
    """Drop stock_market_scores table."""
    op.drop_index('ix_stock_market_scores_date', table_name='stock_market_scores')
    op.drop_index('ix_stock_market_scores_stock_code', table_name='stock_market_scores')
    op.drop_table('stock_market_scores')
