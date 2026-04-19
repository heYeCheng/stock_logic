"""add_lead_concentration_columns

Revision ID: 1fd3d1109b2c
Revises: 20260419_212516
Create Date: 2026-04-19 21:33:35.075028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fd3d1109b2c'
down_revision: Union[str, Sequence[str], None] = '20260419_212516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lead concentration columns to sector_scores table."""
    with op.batch_alter_table('sector_scores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lead_concentration', sa.Numeric(7, 4), nullable=True,
                                      comment='龙头集中度 (归一化 HHI, 0.0000-1.0000)'))
        batch_op.add_column(sa.Column('concentration_interpretation', sa.String(20), nullable=True,
                                      comment='集中度解释 (high/medium/low)'))
        batch_op.add_column(sa.Column('structure_marker', sa.String(20), nullable=True,
                                      comment='结构标记 (聚焦/扩散/快速轮动/正常)'))
        batch_op.add_column(sa.Column('structure_confidence', sa.Float, nullable=True,
                                      comment='结构标记置信度'))


def downgrade() -> None:
    """Remove lead concentration columns from sector_scores table."""
    with op.batch_alter_table('sector_scores', schema=None) as batch_op:
        batch_op.drop_column('structure_confidence')
        batch_op.drop_column('structure_marker')
        batch_op.drop_column('concentration_interpretation')
        batch_op.drop_column('lead_concentration')
