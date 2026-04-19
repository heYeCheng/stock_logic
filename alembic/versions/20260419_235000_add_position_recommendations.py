"""Add position_recommendations table

Revision ID: 20260419_235000
Revises: 20260419_234500
Create Date: 2026-04-19 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260419_235000'
down_revision = '20260419_234500'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create position_recommendations table for EXEC-01: Continuous Position Function.

    This table stores daily position recommendations with macro and sector overlays.
    Position tiers: 空仓 (empty)/轻仓 (light)/中等 (moderate)/重仓 (heavy)/满仓 (full)
    """
    op.create_table(
        'position_recommendations',
        sa.Column('id', sa.Integer(), nullable=False, comment='主键 ID'),
        sa.Column('stock_code', sa.String(20), nullable=False, comment='股票代码 (e.g., 000001.SZ)'),
        sa.Column('snapshot_date', sa.Date(), nullable=False, comment='快照日期'),
        sa.Column('composite_score', sa.Numeric(7, 4), nullable=True, comment='综合分数 (0.0000-1.0000)'),
        sa.Column('macro_multiplier', sa.Numeric(5, 2), nullable=True, comment='宏观乘数 (0.50-1.50)'),
        sa.Column('sector_state', sa.String(20), nullable=True, comment='板块状态 (weak/normal/overheated)'),
        sa.Column('recommended_position', sa.Numeric(7, 4), nullable=True, comment='推荐仓位 (0.0000-1.0000)'),
        sa.Column('position_tier', sa.String(20), nullable=True, comment='仓位层级 (空仓/轻仓/中等/重仓/满仓)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_position_recommendations_code_date')
    )

    op.create_index('ix_position_recommendations_stock_code', 'position_recommendations', ['stock_code'])
    op.create_index('ix_position_recommendations_date', 'position_recommendations', ['snapshot_date'])


def downgrade() -> None:
    """Drop position_recommendations table."""
    op.drop_index('ix_position_recommendations_date', table_name='position_recommendations')
    op.drop_index('ix_position_recommendations_stock_code', table_name='position_recommendations')
    op.drop_table('position_recommendations')
