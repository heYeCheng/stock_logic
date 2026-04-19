"""add hold_decisions table

Revision ID: 20260419_233000
Revises: add_stock_logic_scores, add_stock_market_scores, add_stock_catalysts
Create Date: 2026-04-19 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260419_233000'
down_revision: Union[str, None] = ('add_stock_logic_scores', 'add_stock_market_scores', 'add_stock_catalysts')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hold_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('stock_code', sa.String(20), nullable=False, comment='股票代码'),
        sa.Column('snapshot_date', sa.Date(), nullable=False, comment='快照日期'),
        sa.Column('current_position', sa.Numeric(7, 4), nullable=True, comment='当前持仓数量'),
        sa.Column('action', sa.String(20), nullable=True, comment='决策动作 (hold/sell/reduce)'),
        sa.Column('recommended_position', sa.Numeric(7, 4), nullable=True, comment='推荐持仓数量'),
        sa.Column('action_reason', sa.String(500), nullable=True, comment='决策原因'),
        sa.Column('entry_price', sa.Numeric(10, 4), nullable=True, comment='建仓均价'),
        sa.Column('current_price', sa.Numeric(10, 4), nullable=True, comment='当前价格'),
        sa.Column('pnl_pct', sa.Numeric(7, 4), nullable=True, comment='盈亏百分比'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date', name='uq_hold_decisions_stock_date'),
    )
    op.create_index('ix_hold_decisions_stock_code', 'hold_decisions', ['stock_code'])
    op.create_index('ix_hold_decisions_date', 'hold_decisions', ['snapshot_date'])


def downgrade() -> None:
    op.drop_index('ix_hold_decisions_date', table_name='hold_decisions')
    op.drop_index('ix_hold_decisions_stock_code', table_name='hold_decisions')
    op.drop_table('hold_decisions')
