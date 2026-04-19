"""Add sector_scores table for market layer.

Revision ID: 20260419_212516
Revises: 200d47c66cad
Create Date: 2026-04-19 21:25:16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260419_212516'
down_revision: Union[str, None] = '200d47c66cad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sector_state enum
    sector_state_enum = sa.Enum('weak', 'normal', 'overheated', name='sectorstate')

    op.create_table(
        'sector_scores',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('sector_name', sa.String(100), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('technical_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('composite_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('state', sector_state_enum, nullable=True),
        sa.Column('state_confidence', sa.Float(), nullable=True),
        sa.Column('consecutive_days', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('sector_id', 'snapshot_date', name='uq_sector_scores_sector_date'),
    )
    op.create_index('ix_sector_scores_sector_id', 'sector_scores', ['sector_id'])
    op.create_index('ix_sector_scores_date', 'sector_scores', ['snapshot_date'])


def downgrade() -> None:
    op.drop_table('sector_scores')
    op.execute('DROP TYPE IF EXISTS sectorstate')
