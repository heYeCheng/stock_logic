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
from sqlalchemy.dialects.mysql import JSON

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


class LeaderRole(PyEnum):
    """Leader role classification for stocks within sectors."""
    dragon = "dragon"       # 龙头 - aggressive leader with limit-ups
    zhongjun = "zhongjun"   # 中军 - stable anchor with large cap
    follower = "follower"   # 跟风 - neither dragon nor zhongjun


class StockLeaderRole(Base):
    """Stock leader role classification snapshot.

    Table: stock_leader_roles

    Identifies dragon leader (龙头), zhongjun (中军), and follower (跟风) stocks
    within each sector on a daily basis.
    """

    __tablename__ = "stock_leader_roles"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码 (e.g., 000001.SZ)")
    sector_id = Column(String(50), nullable=False, index=True, comment="板块 ID")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Role classification
    role = Column(String(20), nullable=True, comment="角色分类 (dragon/zhongjun/follower)")

    # Scoring
    dragon_score = Column(Numeric(7, 4), nullable=True, comment="龙头分数 (越高越可能是龙头)")
    zhongjun_score = Column(Numeric(7, 4), nullable=True, comment="中军分数 (越高越可能是中军)")

    # Confidence in role assignment
    confidence = Column(Float, nullable=True, comment="角色分配置信度 (0.0-1.0)")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "sector_id", "snapshot_date", name="uq_stock_leader_roles_stock_sector_date"),
        Index("ix_stock_leader_roles_stock_code", "stock_code"),
        Index("ix_stock_leader_roles_sector_id", "sector_id"),
        Index("ix_stock_leader_roles_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<StockLeaderRole(id={self.id}, stock_code={self.stock_code}, sector_id={self.sector_id}, role={self.role})>"


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


class StockModel(Base):
    """Stock basic information.

    Table: stocks

    Attributes:
        id: Primary key
        ts_code: Stock code (e.g., "000001.SZ")
        name: Stock name
        exchange: Exchange (SH/SZ)
        industry: Industry classification
        keywords: List of keywords associated with the stock
        market_cap: Market capitalization
        list_date: IPO date
    """

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    ts_code = Column(String(20), nullable=False, unique=True, index=True, comment="股票代码 (e.g., 000001.SZ)")
    name = Column(String(50), nullable=True, comment="股票名称")
    exchange = Column(String(10), nullable=True, comment="交易所 (SH/SZ)")
    industry = Column(String(50), nullable=True, comment="所属行业")
    keywords = Column(JSON, nullable=True, comment="关键词列表")
    market_cap = Column(Numeric(15, 2), nullable=True, comment="市值")
    list_date = Column(Date, nullable=True, comment="上市日期")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("ix_stocks_ts_code", "ts_code"),
        Index("ix_stocks_exchange", "exchange"),
        {'extend_existing': True}
    )

    def __repr__(self) -> str:
        return f"<StockModel(id={self.id}, ts_code={self.ts_code}, name={self.name})>"


class StockLogicExposure(Base):
    """Daily stock-logic exposure snapshot.

    Table: stock_logic_exposures

    STOCK-02: Exposure coefficient calculation
    Stores exposure_coefficient = affiliation_strength × logic_match_score
    """

    __tablename__ = "stock_logic_exposures"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    logic_id = Column(String(64), nullable=False, index=True, comment="逻辑 ID")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Exposure calculation components
    exposure_coefficient = Column(Numeric(7, 4), nullable=True, comment="暴露系数 (0.0000-1.0000)")
    affiliation_strength = Column(Numeric(3, 2), nullable=True, comment="关联强度 (0.50-1.00)")
    logic_match_score = Column(Numeric(7, 4), nullable=True, comment="逻辑匹配分数 (0.0000-1.0000)")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "logic_id", "snapshot_date", name="uq_stock_logic_exposures_stock_logic_date"),
        Index("ix_stock_logic_exposures_date", "snapshot_date"),
        Index("ix_stock_logic_exposures_logic", "logic_id"),
    )

    def __repr__(self) -> str:
        return f"<StockLogicExposure(id={self.id}, stock_code={self.stock_code}, logic_id={self.logic_id}, exposure={self.exposure_coefficient})>"


class StockCompositeScore(Base):
    """Daily stock composite score snapshot - 50% logic + 50% market.

    Table: stock_composite_scores

    STOCK-08: Composite Score
    Combines logic score (from STOCK-04) and market score (from STOCK-05)
    to produce a single composite score for stock recommendation ranking.

    Attributes:
        id: Primary key
        stock_code: Stock code (e.g., "000001.SZ")
        snapshot_date: Date of score snapshot
        logic_score: Logic layer score (0.0000-1.0000), from STOCK-04
        market_score: Market layer score (0.0000-1.0000), from STOCK-05
        composite_score: Combined score = (logic + market) / 2
        recommendation_rank: Rank among all stocks (1 = highest composite)
    """

    __tablename__ = "stock_composite_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码 (e.g., 000001.SZ)")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Logic score (0-1 scale) - from STOCK-04
    logic_score = Column(Numeric(7, 4), nullable=True, comment="逻辑分数 (0.0000-1.0000)")

    # Market score (0-1 scale) - from STOCK-05
    market_score = Column(Numeric(7, 4), nullable=True, comment="市场分数 (0.0000-1.0000)")

    # Composite score (0-1 scale)
    composite_score = Column(Numeric(7, 4), nullable=True, comment="综合分数 (logic + market) / 2")

    # Recommendation rank (1 = best)
    recommendation_rank = Column(Integer, nullable=True, comment="推荐排名 (1=最高)")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "snapshot_date", name="uq_stock_composite_scores_code_date"),
        Index("ix_stock_composite_scores_stock_code", "stock_code"),
        Index("ix_stock_composite_scores_date", "snapshot_date"),
        Index("ix_stock_composite_scores_rank", "recommendation_rank"),
    )

    def __repr__(self) -> str:
        return f"<StockCompositeScore(id={self.id}, stock_code={self.stock_code}, date={self.snapshot_date}, composite={self.composite_score}, rank={self.recommendation_rank})>"


class StockLogicScore(Base):
    """Daily stock logic score snapshot - aggregated exposure-weighted logic score.

    Table: stock_logic_scores

    STOCK-04: Stock Logic Score
    Aggregates logic scores weighted by exposure coefficients.

    Formula:
        stock_logic_score = sum(logic_score.decayed_score * exposure) / sum(exposure)

    Attributes:
        id: Primary key
        stock_code: Stock code (e.g., "000001.SZ")
        snapshot_date: Date of score snapshot
        logic_score: Aggregated logic score (0.0000-1.0000)
        total_exposure: Total exposure coefficient across all logics
    """

    __tablename__ = "stock_logic_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码 (e.g., 000001.SZ)")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")

    # Logic score (0-1 scale)
    logic_score = Column(Numeric(7, 4), nullable=True, comment="逻辑分数 (0.0000-1.0000)")

    # Total exposure (for debugging/analysis)
    total_exposure = Column(Numeric(7, 4), nullable=True, comment="总暴露系数 (0.0000+)")

    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("stock_code", "snapshot_date", name="uq_stock_logic_scores_code_date"),
        Index("ix_stock_logic_scores_stock_code", "stock_code"),
        Index("ix_stock_logic_scores_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<StockLogicScore(id={self.id}, stock_code={self.stock_code}, date={self.snapshot_date}, score={self.logic_score})>"


class SectorKeywords(Base):
    """Sector keywords storage for LLM-generated keywords.

    Table: sector_keywords

    STOCK-03: Keyword Auto-Generation
    Stores 5-8 keywords generated by LLM for each sector.
    These keywords are used for:
    - Matching news and events to sectors
    - Linking sectors to investment logics
    - Calculating exposure coefficients

    Attributes:
        id: Primary key
        sector_id: Sector ID (unique)
        sector_name: Human-readable sector name
        keywords: List of 5-8 keywords (JSON array stored as String)
        generated_at: When keywords were generated
        updated_at: Last update timestamp
        generation_source: "llm" (auto-generated) or "manual" (user-provided)
    """

    __tablename__ = "sector_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    sector_id = Column(String(50), nullable=False, unique=True, index=True, comment="板块 ID")
    sector_name = Column(String(100), nullable=True, comment="板块名称")
    keywords = Column(String(500), nullable=True, comment="关键词列表 (JSON 数组，5-8 个关键词)")
    generated_at = Column(DateTime, nullable=True, default=func.now(), comment="生成时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")
    generation_source = Column(String(50), nullable=True, default="llm", comment="生成来源 (llm/manual)")

    __table_args__ = (
        Index("ix_sector_keywords_sector_id", "sector_id"),
    )

    def __repr__(self) -> str:
        return f"<SectorKeywords(id={self.id}, sector_id={self.sector_id}, sector_name={self.sector_name}, keywords={self.keywords})>"
