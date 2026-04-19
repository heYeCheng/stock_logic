"""Logic layer database models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    Text,
    Index,
    UniqueConstraint,
    ForeignKey,
    Numeric,
    Enum,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from src.database.connection import Base


# Enum types for logic layer
class LogicDirection(PyEnum):
    """Logic direction enum."""
    positive = "positive"
    negative = "negative"


class ImportanceLevel(PyEnum):
    """Importance level enum."""
    high = "high"
    medium = "medium"
    low = "low"


class LLMServiceStatus(PyEnum):
    """LLM service health status."""
    full = "full"
    degraded = "degraded"
    offline = "offline"


class LogicModel(Base):
    """Logic model - stores logic definitions and metadata.

    Table: logics
    """

    __tablename__ = "logics"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    logic_id = Column(String(64), nullable=False, unique=True, index=True, comment="逻辑唯一标识符 (e.g., policy_5g_development_001)")
    logic_name = Column(String(256), nullable=False, comment="逻辑名称")
    logic_family = Column(String(128), nullable=False, index=True, comment="逻辑家族 (technology/policy/earnings/m_a/supply_chain)")
    direction = Column(Enum(LogicDirection), nullable=False, comment="逻辑方向 (positive/negative)")
    importance_level = Column(Enum(ImportanceLevel), nullable=False, comment="重要性级别 (high/medium/low)")
    description = Column(Text, nullable=False, comment="逻辑描述")
    keywords = Column(JSON, nullable=True, comment="关键词列表")
    validity_days = Column(Integer, default=30, comment="有效期天数")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否激活")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")

    # Relationships
    events = relationship("EventModel", back_populates="logic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_logics_family_active", "logic_family", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<LogicModel(id={self.id}, logic_id={self.logic_id}, logic_name={self.logic_name})>"


class EventModel(Base):
    """Event model - stores individual events linked to logics.

    Table: events
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    event_id = Column(String(64), nullable=False, unique=True, index=True, comment="事件唯一标识符")
    logic_id = Column(String(64), ForeignKey("logics.logic_id"), nullable=False, index=True, comment="关联逻辑 ID")

    # Event metadata
    event_date = Column(Date, nullable=False, comment="事件日期")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    source = Column(String(50), nullable=False, comment="新闻来源")
    headline = Column(String(500), nullable=True, comment="事件标题")
    content_hash = Column(String(64), nullable=True, comment="内容哈希 (用于去重)")

    # Scoring
    strength_raw = Column(Numeric(5, 4), nullable=False, comment="原始强度 (0.0000-1.0000)")
    strength_adjusted = Column(Numeric(5, 4), nullable=True, comment="调整后强度 (重要性乘数)")
    direction = Column(Enum(LogicDirection), nullable=False, comment="方向 (继承自关联逻辑)")

    # Validity
    validity_start = Column(Date, nullable=True, comment="有效期开始")
    validity_end = Column(Date, nullable=True, comment="有效期结束")
    is_expired = Column(Boolean, nullable=False, default=False, comment="是否已过期")

    # Deduplication
    fingerprint = Column(String(64), nullable=True, index=True, comment="事件指纹 (SHA256)")
    is_duplicate = Column(Boolean, nullable=False, default=False, comment="是否重复事件")

    # Relationships
    logic = relationship("LogicModel", back_populates="events")

    __table_args__ = (
        Index("ix_events_logic_date", "logic_id", "event_date"),
        Index("ix_events_fingerprint", "fingerprint"),
        UniqueConstraint("fingerprint", name="uq_events_fingerprint"),
    )

    def __repr__(self) -> str:
        return f"<EventModel(id={self.id}, event_id={self.event_id}, logic_id={self.logic_id})>"


class LogicScore(Base):
    """Logic score snapshot - daily aggregated scores per logic.

    Table: logic_scores
    """

    __tablename__ = "logic_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    logic_id = Column(String(64), ForeignKey("logics.logic_id"), nullable=False, index=True, comment="关联逻辑 ID")
    snapshot_date = Column(Date, nullable=False, comment="快照日期")

    # Scores
    raw_score = Column(Numeric(7, 4), nullable=True, comment="原始分数 (事件强度总和)")
    decayed_score = Column(Numeric(7, 4), nullable=True, comment="衰减后分数")
    net_thrust = Column(Numeric(7, 4), nullable=True, comment="净推力 (正向 - 负向)")

    # Anti-logic flag
    has_anti_logic = Column(Boolean, nullable=False, default=False, comment="是否存在反身逻辑 (同时存在正向和负向事件)")

    # Event counts
    event_count = Column(Integer, nullable=False, default=0, comment="事件总数")
    positive_event_count = Column(Integer, nullable=False, default=0, comment="正向事件数量")
    negative_event_count = Column(Integer, nullable=False, default=0, comment="负向事件数量")

    # LLM service status
    llm_service_status = Column(Enum(LLMServiceStatus), nullable=True, comment="LLM 服务状态 (full/degraded/offline)")
    fallback_applied = Column(Boolean, nullable=False, default=False, comment="是否启用了降级方案")
    fallback_reason = Column(String(200), nullable=True, comment="降级原因")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("logic_id", "snapshot_date", name="uq_logic_scores_logic_date"),
        Index("ix_logic_scores_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<LogicScore(id={self.id}, logic_id={self.logic_id}, date={self.snapshot_date}, net_thrust={self.net_thrust})>"
