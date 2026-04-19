"""add_stock_logic_exposures table

Revision ID: add_stock_logic_exposures
Revises: bb13c7f87339
Create Date: 2026-04-19 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_logic_exposures'
down_revision: Union[str, Sequence[str], None] = 'bb13c7f87339'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_logic_exposures table for daily stock-logic exposure snapshots."""
    op.create_table(
        'stock_logic_exposures',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('logic_id', sa.String(64), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('exposure_coefficient', sa.Numeric(7, 4), nullable=True),
        sa.Column('affiliation_strength', sa.Numeric(3, 2), nullable=True),
        sa.Column('logic_match_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('stock_code', 'logic_id', 'snapshot_date', name='uq_stock_logic_exposures_stock_logic_date'),
    )
    op.create_index('ix_stock_logic_exposures_date', 'stock_logic_exposures', ['snapshot_date'])
    op.create_index('ix_stock_logic_exposures_logic', 'stock_logic_exposures', ['logic_id'])
    op.create_index('ix_stock_logic_exposures_stock_code', 'stock_logic_exposures', ['stock_code'])


def downgrade() -> None:
    """Drop stock_logic_exposures table."""
    op.drop_index('ix_stock_logic_exposures_stock_code', table_name='stock_logic_exposures')
    op.drop_index('ix_stock_logic_exposures_logic', table_name='stock_logic_exposures')
    op.drop_index('ix_stock_logic_exposures_date', table_name='stock_logic_exposures')
    op.drop_table('stock_logic_exposures')
