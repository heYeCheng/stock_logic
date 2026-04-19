"""add_stock_sector_mappings table

Revision ID: add_stock_sector_mappings
Revises: 1fd3d1109b2c
Create Date: 2026-04-19 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stock_sector_mappings'
down_revision: Union[str, Sequence[str], None] = '1fd3d1109b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_sector_mappings table for stock-sector affiliations."""
    op.create_table(
        'stock_sector_mappings',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('sector_type', sa.String(20), nullable=True),
        sa.Column('sector_name', sa.String(100), nullable=True),
        sa.Column('affiliation_strength', sa.Numeric(3, 2), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        sa.UniqueConstraint('stock_code', 'sector_id', name='uq_stock_sector_stock_code_sector_id'),
    )
    op.create_index('ix_stock_sector_stock_code', 'stock_sector_mappings', ['stock_code'])
    op.create_index('ix_stock_sector_sector_id', 'stock_sector_mappings', ['sector_id'])


def downgrade() -> None:
    """Drop stock_sector_mappings table."""
    op.drop_index('ix_stock_sector_sector_id', table_name='stock_sector_mappings')
    op.drop_index('ix_stock_sector_stock_code', table_name='stock_sector_mappings')
    op.drop_table('stock_sector_mappings')
