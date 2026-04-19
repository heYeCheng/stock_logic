"""add_sector_keywords table

Revision ID: add_sector_keywords
Revises: add_stock_logic_exposures
Create Date: 2026-04-19 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_sector_keywords'
down_revision: Union[str, Sequence[str], None] = 'add_stock_logic_exposures'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sector_keywords table for LLM-generated sector keywords."""
    op.create_table(
        'sector_keywords',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('sector_name', sa.String(100), nullable=True),
        sa.Column('keywords', sa.String(500), nullable=True),
        sa.Column('generated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('generation_source', sa.String(50), nullable=True, server_default='llm'),
        sa.UniqueConstraint('sector_id', name='uq_sector_keywords_sector_id'),
    )
    op.create_index('ix_sector_keywords_sector_id', 'sector_keywords', ['sector_id'])


def downgrade() -> None:
    """Drop sector_keywords table."""
    op.drop_index('ix_sector_keywords_sector_id', table_name='sector_keywords')
    op.drop_table('sector_keywords')
