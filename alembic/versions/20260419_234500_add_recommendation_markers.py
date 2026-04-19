"""Add recommendation_markers table

Revision ID: 20260419_234500
Revises: add_stock_logic_scores, add_stock_market_scores, add_stock_catalysts
Create Date: 2026-04-19 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260419_234500'
down_revision = ('add_stock_logic_scores', 'add_stock_market_scores', 'add_stock_catalysts')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recommendation_markers',
        sa.Column('id', sa.Integer(), nullable=False, comment='主键 ID'),
        sa.Column('stock_code', sa.String(20), nullable=False, comment='股票代码 (e.g., 000001.SZ)'),
        sa.Column('snapshot_date', sa.Date(), nullable=False, comment='快照日期'),
        sa.Column('marker', sa.String(50), nullable=True, comment='标记分类 (逻辑受益股/关联受益股/情绪跟风股)'),
        sa.Column('marker_reason', sa.Text(), nullable=True, comment='分类理由说明'),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True, comment='逻辑分数 (0.0000-1.0000)'),
        sa.Column('market_score', sa.Numeric(7, 4), nullable=True, comment='市场分数 (0.0000-1.0000)'),
        sa.Column('exposure_coefficient', sa.Numeric(7, 4), nullable=True, comment='暴露系数 (0.0000-1.0000)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_recommendation_markers_code_date')
    )

    op.create_index('ix_recommendation_markers_stock_code', 'recommendation_markers', ['stock_code'])
    op.create_index('ix_recommendation_markers_date', 'recommendation_markers', ['snapshot_date'])


def downgrade() -> None:
    op.drop_index('ix_recommendation_markers_date', table_name='recommendation_markers')
    op.drop_index('ix_recommendation_markers_stock_code', table_name='recommendation_markers')
    op.drop_table('recommendation_markers')
