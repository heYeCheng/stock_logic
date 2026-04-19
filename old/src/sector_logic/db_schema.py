# -*- coding: utf-8 -*-
"""
Database schema for Phase 0.5 — trading logic-driven stock selection.

Creates tables for events, logics, and macro_events with CREATE TABLE IF NOT EXISTS
(idempotent — safe to call multiple times).

Uses SQLite-compatible DDL (the project uses SQLite via SQLAlchemy).
"""

import logging
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text,
    Index, UniqueConstraint, DECIMAL,
)
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Separate base to avoid mixing with existing models
SectorLogicBase = declarative_base()


class EventModel(SectorLogicBase):
    """事件记录表 — 每条事件对应一条逻辑的强度变化"""
    __tablename__ = 'sector_logic_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    logic_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)  # 'positive' / 'negative'
    score_impact = Column(Float, nullable=False)
    event_date = Column(Date, nullable=False)
    expire_date = Column(Date, nullable=False)
    summary = Column(Text, nullable=False)
    event_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_events_logic_expire', 'logic_id', 'expire_date'),
        UniqueConstraint('logic_id', 'event_date', 'event_type', 'event_hash',
                         name='uq_logic_date_type_hash'),
    )


class LogicModel(SectorLogicBase):
    """逻辑定义表 — 存储板块的活跃交易逻辑"""
    __tablename__ = 'sector_logic_logics'

    logic_id = Column(String(64), primary_key=True)
    sector_code = Column(String(32), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    direction = Column(String(8), nullable=False)  # 'positive' / 'negative'
    category = Column(String(32), nullable=False)  # 产业趋势/政策驱动/事件驱动/流动性驱动
    importance_level = Column(String(8))  # 高/中/低
    initial_strength = Column(Float)
    current_strength = Column(Float)
    is_active = Column(Boolean, default=True)
    last_event_date = Column(Date)
    last_event_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_logics_sector', 'sector_code', 'is_active'),
    )


class MacroEventModel(SectorLogicBase):
    """宏观事件触发调整表 — 人工录入的重大事件"""
    __tablename__ = 'macro_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False)
    direction = Column(String(8), nullable=False)
    adjustment_value = Column(Float, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_macro_events_active', 'is_active', 'effective_date'),
    )


def init_tables(engine) -> None:
    """Create all sector_logic tables if they don't exist (idempotent)."""
    logger.info("Creating sector_logic tables (if not exists)...")
    SectorLogicBase.metadata.create_all(engine)
    logger.info("sector_logic tables ready: events, logics, macro_events")
