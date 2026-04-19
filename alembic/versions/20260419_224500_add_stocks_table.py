"""add_stocks_table

Revision ID: add_stocks_table
Revises: add_sector_keywords
Create Date: 2026-04-19 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stocks_table'
down_revision: Union[str, None] = 'add_stock_composite_scores'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stocks table for stock basic information."""
    op.create_table(
        'stocks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('ts_code', sa.String(20), nullable=False),
        sa.Column('name', sa.String(50), nullable=True),
        sa.Column('exchange', sa.String(10), nullable=True),
        sa.Column('industry', sa.String(50), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('market_cap', sa.Numeric(15, 2), nullable=True),
        sa.Column('list_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ts_code', name='uq_stocks_ts_code')
    )

    # Create indexes for efficient querying
    op.create_index('ix_stocks_ts_code', 'stocks', ['ts_code'])
    op.create_index('ix_stocks_exchange', 'stocks', ['exchange'])


def downgrade() -> None:
    """Drop stocks table."""
    op.drop_index('ix_stocks_exchange', table_name='stocks')
    op.drop_index('ix_stocks_ts_code', table_name='stocks')
    op.drop_table('stocks')
