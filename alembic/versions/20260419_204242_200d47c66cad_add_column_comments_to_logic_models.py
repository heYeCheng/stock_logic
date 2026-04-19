"""add_column_comments_to_logic_models

Revision ID: 200d47c66cad
Revises: 20260419_200000
Create Date: 2026-04-19 20:42:42.468142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '200d47c66cad'
down_revision: Union[str, Sequence[str], None] = '20260419_200000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Chinese column comments to logic layer tables."""
    # logics table
    with op.batch_alter_table('logics', schema=None) as batch_op:
        batch_op.alter_column('id', existing_type=sa.Integer(), comment='主键 ID')
        batch_op.alter_column('logic_id', existing_type=sa.String(64), comment='逻辑唯一标识符 (e.g., policy_5g_development_001)')
        batch_op.alter_column('logic_name', existing_type=sa.String(256), comment='逻辑名称')
        batch_op.alter_column('logic_family', existing_type=sa.String(128), comment='逻辑家族 (technology/policy/earnings/m_a/supply_chain)')
        batch_op.alter_column('direction', existing_type=sa.Enum('positive', 'negative', name='logicdirection'), comment='逻辑方向 (positive/negative)')
        batch_op.alter_column('importance_level', existing_type=sa.Enum('high', 'medium', 'low', name='importancelevel'), comment='重要性级别 (high/medium/low)')
        batch_op.alter_column('description', existing_type=sa.Text(), comment='逻辑描述')
        # Skip JSON column - MySQL doesn't support COMMENT on JSON type directly
        # batch_op.alter_column('keywords', existing_type=sa.JSON(), comment='关键词列表')
        batch_op.alter_column('validity_days', existing_type=sa.Integer(), comment='有效期天数')
        batch_op.alter_column('is_active', existing_type=sa.Boolean(), comment='是否激活')
        batch_op.alter_column('created_at', existing_type=sa.DateTime(), comment='创建时间')
        batch_op.alter_column('updated_at', existing_type=sa.DateTime(), comment='更新时间')

    # events table
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.alter_column('id', existing_type=sa.Integer(), comment='主键 ID')
        batch_op.alter_column('event_id', existing_type=sa.String(64), comment='事件唯一标识符')
        batch_op.alter_column('logic_id', existing_type=sa.String(64), comment='关联逻辑 ID')
        batch_op.alter_column('event_date', existing_type=sa.Date(), comment='事件日期')
        batch_op.alter_column('created_at', existing_type=sa.DateTime(), comment='创建时间')
        batch_op.alter_column('source', existing_type=sa.String(50), comment='新闻来源')
        batch_op.alter_column('headline', existing_type=sa.String(500), comment='事件标题')
        batch_op.alter_column('content_hash', existing_type=sa.String(64), comment='内容哈希 (用于去重)')
        batch_op.alter_column('strength_raw', existing_type=sa.Numeric(5, 4), comment='原始强度 (0.0000-1.0000)')
        batch_op.alter_column('strength_adjusted', existing_type=sa.Numeric(5, 4), comment='调整后强度 (重要性乘数)')
        batch_op.alter_column('direction', existing_type=sa.Enum('positive', 'negative', name='logicdirection'), comment='方向 (继承自关联逻辑)')
        batch_op.alter_column('validity_start', existing_type=sa.Date(), comment='有效期开始')
        batch_op.alter_column('validity_end', existing_type=sa.Date(), comment='有效期结束')
        batch_op.alter_column('is_expired', existing_type=sa.Boolean(), comment='是否已过期')
        batch_op.alter_column('fingerprint', existing_type=sa.String(64), comment='事件指纹 (SHA256)')
        batch_op.alter_column('is_duplicate', existing_type=sa.Boolean(), comment='是否重复事件')

    # logic_scores table
    with op.batch_alter_table('logic_scores', schema=None) as batch_op:
        batch_op.alter_column('id', existing_type=sa.Integer(), comment='主键 ID')
        batch_op.alter_column('logic_id', existing_type=sa.String(64), comment='关联逻辑 ID')
        batch_op.alter_column('snapshot_date', existing_type=sa.Date(), comment='快照日期')
        batch_op.alter_column('raw_score', existing_type=sa.Numeric(7, 4), comment='原始分数 (事件强度总和)')
        batch_op.alter_column('decayed_score', existing_type=sa.Numeric(7, 4), comment='衰减后分数')
        batch_op.alter_column('net_thrust', existing_type=sa.Numeric(7, 4), comment='净推力 (正向 - 负向)')
        batch_op.alter_column('has_anti_logic', existing_type=sa.Boolean(), comment='是否存在反身逻辑 (同时存在正向和负向事件)')
        batch_op.alter_column('event_count', existing_type=sa.Integer(), comment='事件总数')
        batch_op.alter_column('positive_event_count', existing_type=sa.Integer(), comment='正向事件数量')
        batch_op.alter_column('negative_event_count', existing_type=sa.Integer(), comment='负向事件数量')
        batch_op.alter_column('llm_service_status', existing_type=sa.Enum('full', 'degraded', 'offline', name='llmservicestatus'), comment='LLM 服务状态 (full/degraded/offline)')
        batch_op.alter_column('fallback_applied', existing_type=sa.Boolean(), comment='是否启用了降级方案')
        batch_op.alter_column('fallback_reason', existing_type=sa.String(200), comment='降级原因')
        batch_op.alter_column('created_at', existing_type=sa.DateTime(), comment='创建时间')


def downgrade() -> None:
    """Remove column comments from logic layer tables."""
    # MySQL doesn't have a direct way to drop comments, so we just pass
    # The comments will be overwritten by the next migration
    pass
