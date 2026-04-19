"""Market layer database models for volume-price analysis."""

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
    Numeric,
    Enum,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from src.database.connection import Base


class SectorState(PyEnum):
    """Sector state enumeration for three-state determination."""
    weak = "weak"
    normal = "normal"
    overheated = "overheated"

    @classmethod
    def from_composite_score(
        cls, score: Decimal, previous_state: Optional["SectorState"] = None
    ) -> "SectorState":
        """Determine state with hysteresis.

        Args:
            score: The composite score (0.00-1.00)
            previous_state: Previous state for hysteresis logic, or None for initial

        Returns:
            SectorState based on score and hysteresis thresholds

        Hysteresis thresholds:
            - weak -> normal: requires score > 0.40
            - normal -> overheated: requires score > 0.75
            - overheated -> normal: requires score < 0.65
            - normal -> weak: requires score < 0.30
        """
        if previous_state is None:
            # No history, use simple thresholds
            if score < Decimal("0.35"):
                return cls.weak
            elif score > Decimal("0.70"):
                return cls.overheated
            else:
                return cls.normal

        # Apply hysteresis
        if previous_state == cls.weak:
            return cls.normal if score > Decimal("0.40") else cls.weak
        elif previous_state == cls.overheated:
            return cls.normal if score < Decimal("0.65") else cls.overheated
        else:  # normal
            if score > Decimal("0.75"):
                return cls.overheated
            elif score < Decimal("0.30"):
                return cls.weak
            else:
                return cls.normal


class SectorScore(Base):
    """Sector score snapshot - daily technical and sentiment scores per sector.

    Table: sector_scores
    """

    __tablename__ = "sector_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    sector_id = Column(String(50), nullable=False, index=True, comment="板块 ID")
    sector_name = Column(String(100), nullable=True, comment="板块名称")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Technical score components (0-1 scale)
    technical_score = Column(Numeric(7, 4), nullable=True, comment="技术分数 (0.0000-1.0000)")

    # Sentiment score components (0-1 scale)
    sentiment_score = Column(Numeric(7, 4), nullable=True, comment="情绪分数 (0.0000-1.0000)")

    # Composite score
    composite_score = Column(Numeric(7, 4), nullable=True, comment="综合分数 (technical + sentiment) / 2")

    # State determination
    state = Column(Enum(SectorState), nullable=True, comment="板块状态 (weak/normal/overheated)")
    state_confidence = Column(Float, nullable=True, comment="状态置信度 (0.0-1.0, 距离边界的距离)")
    consecutive_days = Column(Integer, default=0, comment="当前状态连续天数")

    # Lead concentration (HHI-based)
    lead_concentration = Column(Numeric(7, 4), nullable=True, comment="龙头集中度 (归一化 HHI, 0.0000-1.0000)")
    concentration_interpretation = Column(String(20), nullable=True, comment="集中度解释 (high/medium/low)")

    # Structure marker (MARKET-04)
    structure_marker = Column(String(20), nullable=True, comment="结构标记 (聚焦/扩散/快速轮动/正常)")
    structure_confidence = Column(Float, nullable=True, comment="结构标记置信度")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("sector_id", "snapshot_date", name="uq_sector_scores_sector_date"),
        Index("ix_sector_scores_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<SectorScore(id={self.id}, sector_id={self.sector_id}, date={self.snapshot_date}, composite={self.composite_score})>"


class StockSectorMapping(Base):
    """Stock-sector affiliation mapping with industry and concept types.

    Table: stock_sector_mappings

    Attributes:
        id: Primary key
        stock_code: Stock code (e.g., "000001.SZ")
        sector_id: Sector ID (industry or concept ID)
        sector_type: "industry" or "concept"
        sector_name: Human-readable sector name
        affiliation_strength: Strength of affiliation (0.5-1.0)
            - 1.0: Core/primary sector (龙头股)
            - 0.7-0.9: Strong affiliation
            - 0.5-0.6: Weak affiliation (跟风股)
        is_primary: Whether this is the primary sector for the stock
        created_at: Record creation timestamp
        updated_at: Record update timestamp
    """

    __tablename__ = "stock_sector_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    sector_id = Column(String(50), nullable=False, index=True, comment="板块 ID")
    sector_type = Column(String(20), nullable=True, comment="板块类型 (industry/concept)")
    sector_name = Column(String(100), nullable=True, comment="板块名称")
    affiliation_strength = Column(Numeric(3, 2), nullable=True, default=Decimal("1.0"), comment="关联强度 (0.50-1.00)")
    is_primary = Column(Boolean, nullable=True, default=False, comment="是否为主板块")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "sector_id", name="uq_stock_sector_stock_code_sector_id"),
        Index("ix_stock_sector_stock_code", "stock_code"),
        Index("ix_stock_sector_sector_id", "sector_id"),
    )

    def __repr__(self) -> str:
        return f"<StockSectorMapping(id={self.id}, stock_code={self.stock_code}, sector_id={self.sector_id}, type={self.sector_type}, strength={self.affiliation_strength})>"


class StockMarketScore(Base):
    """Individual stock market score snapshot - daily technical and sentiment scores per stock.

    Table: stock_market_scores

    STOCK-05: Stock Market Radar
    Implements technical + sentiment scores from pure volume-price data.
    """

    __tablename__ = "stock_market_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码 (e.g., 000001.SZ)")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Technical score (0-1 scale)
    technical_score = Column(Numeric(7, 4), nullable=True, comment="技术分数 (0.0000-1.0000)")

    # Sentiment score (0-1 scale)
    sentiment_score = Column(Numeric(7, 4), nullable=True, comment="情绪分数 (0.0000-1.0000)")

    # Composite score
    market_composite = Column(Numeric(7, 4), nullable=True, comment="综合市场分数 (technical + sentiment) / 2")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "snapshot_date", name="uq_stock_market_scores_code_date"),
        Index("ix_stock_market_scores_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<StockMarketScore(id={self.id}, stock_code={self.stock_code}, date={self.snapshot_date}, composite={self.market_composite})>"
