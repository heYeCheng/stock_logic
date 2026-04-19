---
plan_id: STOCK-01
phase: 4
requirement: STOCK-01
title: Stock-Sector Mapping Table
description: Create stock-sector affiliation table with industry and concept mappings
type: feature
estimated_effort: 1.5h
---

# Plan: STOCK-01 - Stock-Sector Mapping Table

## Goal
Create stock-sector mapping table that maintains industry and concept affiliations with strength tracking.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-01 section)
- Models: src/market/models.py
- Dependencies: Phase 1 data infrastructure

## Data Model

```python
class StockSectorMapping(Base):
    __tablename__ = "stock_sector_mappings"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    sector_id = Column(String(50), nullable=False, index=True)
    sector_type = Column(String(20))  # "industry" or "concept"
    sector_name = Column(String(100))
    affiliation_strength = Column(Numeric(3, 2), default=1.0)  # 0.5-1.0
    is_primary = Column(Boolean, default=False)  # Primary sector
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

## Affiliation Strength Rules
- **1.0**: Core/primary sector (龙头股)
- **0.7-0.9**: Strong affiliation
- **0.5-0.6**: Weak affiliation (跟风股)

## Tasks

### Task 1: Create StockSectorMapping model
**File**: `src/market/models.py` (append)

```python
class StockSectorMapping(Base):
    """Stock-sector affiliation mapping."""
    __tablename__ = "stock_sector_mappings"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    sector_id = Column(String(50), nullable=False, index=True)
    sector_type = Column(String(20))  # industry/concept
    sector_name = Column(String(100))
    affiliation_strength = Column(Numeric(3, 2), default=Decimal("1.0"))
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'sector_id'),
    )
```

### Task 2: Create TushareSectorFetcher
**File**: `src/data/tushare_fetcher.py` (append)

```python
class TushareFetcher:
    async def fetch_sector_constituents(self, sector_id: str) -> List[dict]:
        """
        Fetch sector constituents from Tushare.
        
        API: index_member (for industry indices)
        """
        try:
            df = await self.pro.index_member(
                index_code=sector_id
            )
            
            records = []
            for _, row in df.iterrows():
                records.append({
                    "stock_code": row.get("ts_code"),
                    "sector_id": sector_id,
                    "sector_name": row.get("index_name"),
                    "is_primary": True,  # Index constituent = primary
                })
            
            return records
        except Exception as e:
            logger.error(f"Failed to fetch sector constituents: {e}")
            return []
    
    async def fetch_concept_constituents(self, concept_id: str) -> List[dict]:
        """
        Fetch concept sector constituents.
        
        API: concept_detail
        """
        try:
            df = await self.pro.concept_detail(
                concept_id=concept_id
            )
            
            records = []
            for _, row in df.iterrows():
                records.append({
                    "stock_code": row.get("ts_code"),
                    "sector_id": concept_id,
                    "sector_type": "concept",
                    "sector_name": row.get("concept_name"),
                    "is_primary": False,  # Concept = secondary
                })
            
            return records
        except Exception as e:
            logger.error(f"Failed to fetch concept constituents: {e}")
            return []
```

### Task 3: Create StockSectorService
**File**: `src/market/sector_mapping.py` (create)

```python
class StockSectorService:
    """Manage stock-sector mappings."""
    
    async def update_sector_mappings(
        self,
        stock_code: str,
        mappings: List[dict]
    ) -> None:
        """Update mappings for a stock."""
        async with async_session_maker() as session:
            # Delete old mappings
            await session.execute(
                delete(StockSectorMapping).where(
                    StockSectorMapping.stock_code == stock_code
                )
            )
            
            # Insert new mappings
            for mapping in mappings:
                record = StockSectorMapping(stock_code=stock_code, **mapping)
                session.add(record)
            
            await session.commit()
    
    async def get_stock_sectors(self, stock_code: str) -> List[StockSectorMapping]:
        """Get all sectors for a stock."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockSectorMapping).where(
                    StockSectorMapping.stock_code == stock_code
                ).order_by(StockSectorMapping.is_primary.desc())
            )
            return result.scalars().all()
    
    async def get_sector_stocks(self, sector_id: str) -> List[str]:
        """Get all stocks in a sector."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockSectorMapping.stock_code).where(
                    StockSectorMapping.sector_id == sector_id
                )
            )
            return result.scalars().all()
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_sector_mappings.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_sector_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('sector_type', sa.String(20), nullable=True),
        sa.Column('sector_name', sa.String(100), nullable=True),
        sa.Column('affiliation_strength', sa.Numeric(3, 2), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'sector_id')
    )
    
    op.create_index('idx_stock', 'stock_sector_mappings', ['stock_code'])
    op.create_index('idx_sector', 'stock_sector_mappings', ['sector_id'])
```

### Task 5: Create unit tests
**File**: `tests/test_sector_mapping.py`

Test cases:
- Model creation
- Fetch sector constituents (mock)
- Fetch concept constituents (mock)
- Update mappings
- Get stock sectors
- Get sector stocks
- Affiliation strength validation

## Success Criteria
- [ ] StockSectorMapping model created
- [ ] TushareFetcher can fetch constituents
- [ ] StockSectorService manages mappings
- [ ] Migration runs successfully
- [ ] Unit tests pass

## Dependencies
- INFRA-01: Database models (completed)
- INFRA-02: Tushare fetcher (completed)

## Notes
- Mappings refreshed periodically (weekly)
- Primary sector determines main affiliation
- Multiple concept affiliations allowed
