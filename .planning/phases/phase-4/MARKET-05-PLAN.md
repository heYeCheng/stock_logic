---
plan_id: MARKET-05
phase: 4
requirement: MARKET-05
title: Tushare Limit Board Data
description: Implement Tushare limit-up/limit-down data ingestion
type: feature
estimated_effort: 1.5h
---

# Plan: MARKET-05 - Tushare Limit Board Data

## Goal
Implement Tushare limit board data ingestion (limit_list, top_inst) for sentiment analysis.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (MARKET-05 section)
- Models: src/market/models.py (to be created)
- Dependencies: INFRA-02 (Tushare fetcher)

## Data Tables

### limit_list Table
```sql
CREATE TABLE tushare_limit_list (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    name VARCHAR(50),
    type ENUM('limit_up', 'limit_down', 'st_limit_up', 'st_limit_down'),
    limit_amount DECIMAL(15, 2),
    close_price DECIMAL(15, 2),
    open_count INT,
    first_time TIME,
    last_time TIME,
    strong_close ENUM('strong', 'normal', 'weak'),
    INDEX idx_date (trade_date),
    INDEX idx_code (ts_code)
);
```

### top_inst Table
```sql
CREATE TABLE tushare_top_inst (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(50),
    side ENUM('buy', 'sell'),
    broker VARCHAR(100),
    amount DECIMAL(15, 2),
    net_amount DECIMAL(15, 2),
    rank INT,
    INDEX idx_date_code (trade_date, ts_code)
);
```

## Tasks

### Task 1: Create TushareLimitModel
**File**: `src/market/models.py` (append)

```python
class TushareLimitList(Base):
    __tablename__ = "tushare_limit_list"
    
    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False, index=True)
    ts_code = Column(String(20), nullable=False, index=True)
    exchange = Column(String(10))
    name = Column(String(50))
    type = Column(String(20))  # limit_up/limit_down/st_limit_up/st_limit_down
    limit_amount = Column(Numeric(15, 2))
    close_price = Column(Numeric(15, 2))
    open_count = Column(Integer)
    first_time = Column(Time)
    last_time = Column(Time)
    strong_close = Column(String(20))  # strong/normal/weak
    
    __table_args__ = (
        UniqueConstraint('trade_date', 'ts_code'),
    )

class TushareTopInst(Base):
    __tablename__ = "tushare_top_inst"
    
    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False, index=True)
    ts_code = Column(String(20), nullable=False, index=True)
    name = Column(String(50))
    side = Column(String(10))  # buy/sell
    broker = Column(String(100))
    amount = Column(Numeric(15, 2))
    net_amount = Column(Numeric(15, 2))
    rank = Column(Integer)
```

### Task 2: Implement LimitListFetcher
**File**: `src/data/tushare_fetcher.py` (append)

```python
class TushareFetcher:
    async def fetch_limit_list(self, trade_date: date) -> List[dict]:
        """
        Fetch limit board data for a trading day.
        
        API: limit_list
        """
        try:
            df = await self.pro.limit_list(
                trade_date=trade_date.strftime("%Y%m%d")
            )
            
            records = []
            for _, row in df.iterrows():
                records.append({
                    "trade_date": trade_date,
                    "ts_code": row.get("ts_code"),
                    "exchange": row.get("exchange"),
                    "name": row.get("name"),
                    "type": self._classify_limit_type(row),
                    "limit_amount": row.get("limit_amount"),
                    "close_price": row.get("close"),
                    "open_count": row.get("open_times"),
                    "first_time": self._parse_time(row.get("first_time")),
                    "last_time": self._parse_time(row.get("last_time")),
                    "strong_close": self._classify_strong_close(row),
                })
            
            return records
        except Exception as e:
            logger.error(f"Failed to fetch limit_list: {e}")
            return []
    
    def _classify_limit_type(self, row: dict) -> str:
        """Classify limit type."""
        if row.get("limit", "") == "U":  # Limit up
            if "ST" in row.get("name", ""):
                return "st_limit_up"
            return "limit_up"
        elif row.get("limit", "") == "D":  # Limit down
            if "ST" in row.get("name", ""):
                return "st_limit_down"
            return "limit_down"
        else:
            return "unknown"
    
    def _classify_strong_close(self, row: dict) -> str:
        """Classify strength of close."""
        open_times = row.get("open_times", 0)
        if open_times == 0:
            return "strong"  # Never opened
        elif open_times <= 3:
            return "normal"
        else:
            return "weak"  # Frequently opened
```

### Task 3: Implement TopInstFetcher
**File**: `src/data/tushare_fetcher.py` (append)

```python
class TushareFetcher:
    async def fetch_top_inst(self, trade_date: date) -> List[dict]:
        """
        Fetch top institutional buyers/sellers.
        
        API: top_inst
        """
        try:
            df = await self.pro.top_inst(
                trade_date=trade_date.strftime("%Y%m%d")
            )
            
            records = []
            for _, row in df.iterrows():
                records.append({
                    "trade_date": trade_date,
                    "ts_code": row.get("ts_code"),
                    "name": row.get("name"),
                    "side": "buy" if row.get("side") == "buy" else "sell",
                    "broker": row.get("broker"),
                    "amount": row.get("amount"),
                    "net_amount": row.get("net_amount"),
                    "rank": row.get("rank"),
                })
            
            return records
        except Exception as e:
            logger.error(f"Failed to fetch top_inst: {e}")
            return []
```

### Task 4: Create persistence service
**File**: `src/market/limit_board.py` (create)

```python
class LimitBoardService:
    """Persist and query limit board data."""
    
    async def persist_limit_list(self, records: List[dict]) -> int:
        """Persist limit list records."""
        async with async_session_maker() as session:
            count = 0
            for record in records:
                limit = TushareLimitList(**record)
                session.add(limit)
                count += 1
            await session.commit()
        return count
    
    async def persist_top_inst(self, records: List[dict]) -> int:
        """Persist top inst records."""
        async with async_session_maker() as session:
            count = 0
            for record in records:
                inst = TushareTopInst(**record)
                session.add(inst)
                count += 1
            await session.commit()
        return count
    
    async def get_limit_up_count(self, trade_date: date, sector_id: str = None) -> int:
        """Get count of limit-up stocks."""
        async with async_session_maker() as session:
            query = select(func.count()).where(
                TushareLimitList.trade_date == trade_date,
                TushareLimitList.type.in_(["limit_up", "st_limit_up"])
            )
            if sector_id:
                # Join with sector mappings
                pass
            result = await session.execute(query)
            return result.scalar()
```

### Task 5: Create Alembic migration
**File**: `alembic/versions/xxxx_add_limit_board_tables.py` (create)

```python
def upgrade() -> None:
    op.create_table('tushare_limit_list',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('ts_code', sa.String(20), nullable=False),
        sa.Column('exchange', sa.String(10), nullable=True),
        sa.Column('name', sa.String(50), nullable=True),
        sa.Column('type', sa.String(20), nullable=True),
        sa.Column('limit_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('close_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('open_count', sa.Integer(), nullable=True),
        sa.Column('first_time', sa.Time(), nullable=True),
        sa.Column('last_time', sa.Time(), nullable=True),
        sa.Column('strong_close', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trade_date', 'ts_code')
    )
    
    op.create_index('idx_date', 'tushare_limit_list', ['trade_date'])
    op.create_index('idx_code', 'tushare_limit_list', ['ts_code'])
    
    # Similar for tushare_top_inst
```

### Task 6: Create unit tests
**File**: `tests/test_limit_board.py`

Test cases:
- Limit list fetch (mock API)
- Top inst fetch (mock API)
- Persistence works correctly
- Query methods return correct data
- Limit type classification
- Strong close classification

## Success Criteria
- [ ] TushareLimitList and TushareTopInst models created
- [ ] TushareFetcher can fetch limit_list and top_inst
- [ ] Data persists correctly
- [ ] Query methods work
- [ ] Migration runs successfully
- [ ] Unit tests pass

## Dependencies
- INFRA-02: Tushare fetcher (completed)
- INFRA-01: Database models (completed)

## Notes
- Limit board data used for sentiment analysis
- Top inst data shows institutional activity
- Data refreshes daily after market close
