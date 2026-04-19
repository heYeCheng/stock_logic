"""Add logic layer tables - logics, events, logic_scores.

Revision ID: 20260419_200000
Revises: 119468b7c4f7
Create Date: 2026-04-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260419_200000'
down_revision: Union[str, None] = '119468b7c4f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    logic_direction_enum = sa.Enum('positive', 'negative', name='logicdirection')
    importance_level_enum = sa.Enum('high', 'medium', 'low', name='importancelevel')
    llm_service_status_enum = sa.Enum('full', 'degraded', 'offline', name='llmservicestatus')

    op.create_table(
        'logics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('logic_id', sa.String(64), nullable=False),
        sa.Column('logic_name', sa.String(256), nullable=False),
        sa.Column('logic_family', sa.String(128), nullable=False),
        sa.Column('direction', logic_direction_enum, nullable=False),
        sa.Column('importance_level', importance_level_enum, nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('keywords', sa.Text(), nullable=True),  # JSON stored as TEXT for MySQL 5.7 compatibility
        sa.Column('validity_days', sa.Integer(), nullable=True, default=30),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('logic_id', name='uq_logics_logic_id'),
    )
    op.create_index('ix_logics_logic_id', 'logics', ['logic_id'])
    op.create_index('ix_logics_family', 'logics', ['logic_family'])
    op.create_index('ix_logics_family_active', 'logics', ['logic_family', 'is_active'])

    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(64), nullable=False),
        sa.Column('logic_id', sa.String(64), sa.ForeignKey('logics.logic_id'), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('headline', sa.String(500), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('strength_raw', sa.Numeric(5, 4), nullable=False),
        sa.Column('strength_adjusted', sa.Numeric(5, 4), nullable=True),
        sa.Column('direction', logic_direction_enum, nullable=False),
        sa.Column('validity_start', sa.Date(), nullable=True),
        sa.Column('validity_end', sa.Date(), nullable=True),
        sa.Column('is_expired', sa.Boolean(), nullable=False, default=False),
        sa.Column('fingerprint', sa.String(64), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, default=False),
        sa.UniqueConstraint('event_id', name='uq_events_event_id'),
        sa.UniqueConstraint('fingerprint', name='uq_events_fingerprint'),
    )
    op.create_index('ix_events_event_id', 'events', ['event_id'])
    op.create_index('ix_events_logic_id', 'events', ['logic_id'])
    op.create_index('ix_events_logic_date', 'events', ['logic_id', 'event_date'])
    op.create_index('ix_events_fingerprint', 'events', ['fingerprint'])

    op.create_table(
        'logic_scores',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('logic_id', sa.String(64), sa.ForeignKey('logics.logic_id'), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('raw_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('decayed_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('net_thrust', sa.Numeric(7, 4), nullable=True),
        sa.Column('has_anti_logic', sa.Boolean(), nullable=False, default=False),
        sa.Column('event_count', sa.Integer(), nullable=False, default=0),
        sa.Column('positive_event_count', sa.Integer(), nullable=False, default=0),
        sa.Column('negative_event_count', sa.Integer(), nullable=False, default=0),
        sa.Column('llm_service_status', llm_service_status_enum, nullable=True),
        sa.Column('fallback_applied', sa.Boolean(), nullable=False, default=False),
        sa.Column('fallback_reason', sa.String(200), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('logic_id', 'snapshot_date', name='uq_logic_scores_logic_date'),
    )
    op.create_index('ix_logic_scores_logic_id', 'logic_scores', ['logic_id'])
    op.create_index('ix_logic_scores_date', 'logic_scores', ['snapshot_date'])


def downgrade() -> None:
    op.drop_table('logic_scores')
    op.drop_table('events')
    op.drop_table('logics')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS logicdirection')
    op.execute('DROP TYPE IF EXISTS importancelevel')
    op.execute('DROP TYPE IF EXISTS llmservicestatus')
