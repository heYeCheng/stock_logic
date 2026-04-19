"""add_stock_catalysts

Revision ID: add_stock_catalysts
Revises: add_stocks_table
Create Date: 2026-04-19 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_catalysts'
down_revision: Union[str, None] = 'add_stocks_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_catalysts table for catalyst marker classification."""
    op.create_table(
        'stock_catalysts',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('catalyst_level', sa.String(20), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=True),
        sa.Column('high_importance_count', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_stock_catalysts_code_date')
    )

    # Create indexes for efficient querying
    op.create_index('ix_stock_catalysts_stock_code', 'stock_catalysts', ['stock_code'])
    op.create_index('ix_stock_catalysts_date', 'stock_catalysts', ['snapshot_date'])


def downgrade() -> None:
    """Drop stock_catalysts table."""
    op.drop_index('ix_stock_catalysts_date', table_name='stock_catalysts')
    op.drop_index('ix_stock_catalysts_stock_code', table_name='stock_catalysts')
    op.drop_table('stock_catalysts')
