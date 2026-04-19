"""ORM models for stocks, market_data, and macro_snapshot.

Note: EventModel and LogicModel have been moved to src/logic/models.py
as part of the Logic Layer refactoring.
"""

from datetime import date, datetime
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
    BigInteger,
    func,
    Numeric,
    Enum,
)

from src.database.connection import Base


# Enum types for macro snapshot
class MonetaryConditionEnum(PyEnum):
    wide = "wide"
    neutral = "neutral"
    tight = "tight"


class CreditConditionEnum(PyEnum):
    wide = "wide"
    neutral = "neutral"
    tight = "tight"


class QuadrantEnum(PyEnum):
    wide_wide = "wide-wide"
    wide_tight = "wide-tight"
    tight_wide = "tight-wide"
    tight_tight = "tight-tight"


class StockModel(Base):
    """Stock model - stores stock metadata.

    Table: stocks
    """

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(16), nullable=False, unique=True, index=True)
    name = Column(String(64), nullable=False)
    industry = Column(String(128), nullable=True)
    concept_sectors = Column(Text, nullable=True)
    listed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (Index("ix_stocks_code", "ts_code"),)

    def __repr__(self) -> str:
        return f"<StockModel(id={self.id}, ts_code={self.ts_code}, name={self.name})>"


class MarketDataModel(Base):
    """Market data model - stores daily OHLCV data.

    Table: market_data
    """

    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(16), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String(32), nullable=False)  # 'tushare' / 'akshare' / 'efinance'
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_market_data_code_date", "ts_code", "trade_date"),
        UniqueConstraint(
            "ts_code", "trade_date", name="uq_market_data_code_date"
        ),
    )

    def __repr__(self) -> str:
        return f"<MarketDataModel(id={self.id}, ts_code={self.ts_code}, trade_date={self.trade_date})>"


class MacroSnapshot(Base):
    """Macro snapshot model - stores monthly macro environment scores.

    Table: macro_snapshot
    """

    __tablename__ = "macro_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Liquidity dimension
    m2_yoy = Column(Numeric(5, 2), nullable=True)  # M2 YoY %
    dr007_avg = Column(Numeric(5, 4), nullable=True)  # DR007 avg %
    bond_10y_yield = Column(Numeric(5, 4), nullable=True)  # 10Y bond yield %
    liquidity_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Growth dimension
    gdp_yoy = Column(Numeric(5, 2), nullable=True)  # GDP YoY %
    pmi_manufacturing = Column(Numeric(5, 2), nullable=True)  # Manufacturing PMI
    industrial_prod_yoy = Column(Numeric(5, 2), nullable=True)  # Industrial prod YoY %
    growth_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Inflation dimension
    cpi_yoy = Column(Numeric(5, 2), nullable=True)  # CPI YoY %
    ppi_yoy = Column(Numeric(5, 2), nullable=True)  # PPI YoY %
    inflation_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Policy dimension (simplified - scored based on data availability)
    policy_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Global dimension
    fed_rate = Column(Numeric(5, 4), nullable=True)  # Fed funds rate %
    dxy_index = Column(Numeric(6, 2), nullable=True)  # Dollar Index
    us_cn_spread = Column(Numeric(5, 4), nullable=True)  # US-CN 10Y spread %
    global_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Composite score
    composite_score = Column(Numeric(3, 2), nullable=True)  # -1.0 to +1.0

    # Quadrant classification
    monetary_condition = Column(Enum(MonetaryConditionEnum), nullable=True)
    credit_condition = Column(Enum(CreditConditionEnum), nullable=True)
    quadrant = Column(Enum(QuadrantEnum), nullable=True)
    macro_multiplier = Column(Numeric(4, 3), nullable=True)  # 0.85 to 1.15

    __table_args__ = (Index("ix_macro_snapshot_date", "snapshot_date"),)

    def __repr__(self) -> str:
        return f"<MacroSnapshot(id={self.id}, date={self.snapshot_date}, quadrant={self.quadrant}, multiplier={self.macro_multiplier})>"


class TushareLimitList(Base):
    """Tushare limit board data - daily limit-up/limit-down stocks.

    Table: tushare_limit_list
    """

    __tablename__ = "tushare_limit_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True)
    ts_code = Column(String(20), nullable=False, index=True)
    exchange = Column(String(10), nullable=True)
    name = Column(String(50), nullable=True)
    type = Column(String(20), nullable=True)  # limit_up/limit_down/st_limit_up/st_limit_down
    limit_amount = Column(Numeric(15, 2), nullable=True)
    close_price = Column(Numeric(15, 2), nullable=True)
    open_count = Column(Integer, nullable=True)
    first_time = Column(String(20), nullable=True)  # Stored as HH:mm:ss string
    last_time = Column(String(20), nullable=True)  # Stored as HH:mm:ss string
    strong_close = Column(String(20), nullable=True)  # strong/normal/weak

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_limit_list_date_code"),
        Index("idx_date", "trade_date"),
        Index("idx_code", "ts_code"),
    )

    def __repr__(self) -> str:
        return f"<TushareLimitList(id={self.id}, trade_date={self.trade_date}, ts_code={self.ts_code}, type={self.type})>"


class TushareTopInst(Base):
    """Tushare top institutional buyers/sellers on limit days.

    Table: tushare_top_inst
    """

    __tablename__ = "tushare_top_inst"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True)
    ts_code = Column(String(20), nullable=False, index=True)
    name = Column(String(50), nullable=True)
    side = Column(String(10), nullable=True)  # buy/sell
    broker = Column(String(100), nullable=True)
    amount = Column(Numeric(15, 2), nullable=True)
    net_amount = Column(Numeric(15, 2), nullable=True)
    rank = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", "side", "rank", name="uq_top_inst_date_code_side_rank"),
        Index("idx_date_code", "trade_date", "ts_code"),
    )

    def __repr__(self) -> str:
        return f"<TushareTopInst(id={self.id}, trade_date={self.trade_date}, ts_code={self.ts_code}, side={self.side})>"
