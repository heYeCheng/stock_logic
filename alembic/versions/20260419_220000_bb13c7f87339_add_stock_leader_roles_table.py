"""add_stock_leader_roles_table

Revision ID: bb13c7f87339
Revises: 20260419_214500_add_stock_sector_mappings
Create Date: 2026-04-19 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb13c7f87339'
down_revision: Union[str, None] = 'add_stock_sector_mappings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_leader_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False, comment='股票代码 (e.g., 000001.SZ)'),
        sa.Column('sector_id', sa.String(50), nullable=False, comment='板块 ID'),
        sa.Column('snapshot_date', sa.Date(), nullable=False, comment='快照日期'),
        sa.Column('role', sa.String(20), nullable=True, comment='角色分类 (dragon/zhongjun/follower)'),
        sa.Column('dragon_score', sa.Numeric(7, 4), nullable=True, comment='龙头分数 (越高越可能是龙头)'),
        sa.Column('zhongjun_score', sa.Numeric(7, 4), nullable=True, comment='中军分数 (越高越可能是中军)'),
        sa.Column('confidence', sa.Float(), nullable=True, comment='角色分配置信度 (0.0-1.0)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'sector_id', 'snapshot_date', name='uq_stock_leader_roles_stock_sector_date'),
        comment='Stock leader role classification snapshot'
    )

    op.create_index('ix_stock_leader_roles_stock_code', 'stock_leader_roles', ['stock_code'])
    op.create_index('ix_stock_leader_roles_sector_id', 'stock_leader_roles', ['sector_id'])
    op.create_index('ix_stock_leader_roles_date', 'stock_leader_roles', ['snapshot_date'])


def downgrade() -> None:
    op.drop_index('ix_stock_leader_roles_date', table_name='stock_leader_roles')
    op.drop_index('ix_stock_leader_roles_sector_id', table_name='stock_leader_roles')
    op.drop_index('ix_stock_leader_roles_stock_code', table_name='stock_leader_roles')
    op.drop_table('stock_leader_roles')
