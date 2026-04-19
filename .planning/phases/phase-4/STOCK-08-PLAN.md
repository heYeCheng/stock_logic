---
plan_id: STOCK-08
phase: 4
requirement: STOCK-08
title: Composite Score
description: Calculate individual stock composite score (50% logic + 50% market)
type: feature
estimated_effort: 0.5h
---

# Plan: STOCK-08 - Composite Score

## Goal
Implement individual stock composite score calculation: 50% logic score + 50% market score.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-08 section)
- Models: src/market/models.py
- Dependencies: STOCK-04 (logic score), STOCK-05 (market score)

## Formula

```python
def compute_composite_score(stock_logic_score, stock_market_score):
    """
    50% logic + 50% market
    """
    return (stock_logic_score + stock_market_score) / 2
```

## Tasks

### Task 1: Create StockCompositeScore model
**File**: `src/market/models.py` (append)

```python
class StockCompositeScore(Base):
    """Daily stock composite score snapshot."""
    __tablename__ = "stock_composite_scores"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    logic_score = Column(Numeric(7, 4))  # From STOCK-04
    market_score = Column(Numeric(7, 4))  # From STOCK-05
    composite_score = Column(Numeric(7, 4))  # (logic + market) / 2
    recommendation_rank = Column(Integer)  # Ranked among all stocks
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create CompositeScoreService
**File**: `src/market/composite.py` (create)

```python
from decimal import Decimal
from typing import Dict, List, Optional

class CompositeScoreService:
    """Calculate stock composite scores."""
    
    def calculate_composite(
        self,
        logic_score: Decimal,
        market_score: Decimal
    ) -> Decimal:
        """
        Calculate composite score.
        
        Formula: (logic + market) / 2
        
        Args:
            logic_score: Stock logic score (0-1)
            market_score: Stock market score (0-1)
        
        Returns:
            Composite score (0-1)
        """
        return (logic_score + market_score) / Decimal("2")
    
    def calculate_rank(
        self,
        stock_code: str,
        composite_scores: Dict[str, Decimal]
    ) -> int:
        """
        Calculate recommendation rank for a stock.
        
        Args:
            stock_code: Stock code
            composite_scores: Dict[stock_code, composite_score]
        
        Returns:
            Rank (1 = highest composite score)
        """
        if stock_code not in composite_scores:
            return 0
        
        score = composite_scores[stock_code]
        
        # Count stocks with higher scores
        rank = sum(1 for s in composite_scores.values() if s > score) + 1
        
        return rank
    
    async def generate_snapshot(
        self,
        snapshot_date: date
    ) -> List[StockCompositeScore]:
        """Generate composite score snapshots for all stocks."""
        
        # Get logic scores
        logic_scores = await self._get_logic_scores(snapshot_date)
        
        # Get market scores
        market_scores = await self._get_market_scores(snapshot_date)
        
        # Calculate composites
        composites = {}
        records = []
        
        all_stocks = set(logic_scores.keys()) | set(market_scores.keys())
        
        for stock_code in all_stocks:
            logic = logic_scores.get(stock_code, Decimal("0"))
            market = market_scores.get(stock_code, Decimal("0"))
            
            composite = self.calculate_composite(logic, market)
            composites[stock_code] = composite
        
        # Calculate ranks
        for stock_code, composite in composites.items():
            rank = self.calculate_rank(stock_code, composites)
            
            record = StockCompositeScore(
                stock_code=stock_code,
                snapshot_date=snapshot_date,
                logic_score=logic_scores.get(stock_code, Decimal("0")),
                market_score=market_scores.get(stock_code, Decimal("0")),
                composite_score=composite,
                recommendation_rank=rank
            )
            
            records.append(record)
        
        # Persist all
        await self._persist_batch(records)
        return records
```

### Task 3: Create query interface
**File**: `src/market/composite.py` (append)

```python
class CompositeQueries:
    """Query composite scores."""
    
    @staticmethod
    async def get_top_stocks(
        snapshot_date: date,
        limit: int = 20
    ) -> List[StockCompositeScore]:
        """Get top N stocks by composite score."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockCompositeScore)
                .where(StockCompositeScore.snapshot_date == snapshot_date)
                .order_by(StockCompositeScore.composite_score.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    @staticmethod
    async def get_stock_composite(
        stock_code: str,
        snapshot_date: date
    ) -> Optional[StockCompositeScore]:
        """Get composite score for a specific stock."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockCompositeScore).where(
                    StockCompositeScore.stock_code == stock_code,
                    StockCompositeScore.snapshot_date == snapshot_date
                )
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_stocks_by_rank_range(
        snapshot_date: date,
        min_rank: int,
        max_rank: int
    ) -> List[StockCompositeScore]:
        """Get stocks within a rank range."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockCompositeScore)
                .where(StockCompositeScore.snapshot_date == snapshot_date)
                .where(StockCompositeScore.recommendation_rank >= min_rank)
                .where(StockCompositeScore.recommendation_rank <= max_rank)
                .order_by(StockCompositeScore.recommendation_rank)
            )
            return result.scalars().all()
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_composite_scores.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_composite_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('market_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('composite_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('recommendation_rank', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'stock_composite_scores', ['stock_code'])
    op.create_index('idx_date', 'stock_composite_scores', ['snapshot_date'])
    op.create_index('idx_rank', 'stock_composite_scores', ['recommendation_rank'])
```

### Task 5: Create unit tests
**File**: `tests/test_composite.py`

Test cases:
- Composite calculation (equal weights)
- Composite calculation (logic only)
- Composite calculation (market only)
- Rank calculation
- Top stocks query
- Stock-specific query
- Rank range query

## Success Criteria
- [ ] CompositeScoreService calculates correctly
- [ ] StockCompositeScore model created
- [ ] Query methods work
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- STOCK-04: Stock logic score (completed)
- STOCK-05: Stock market score (completed)

## Notes
- 50/50 weighting is simple and interpretable
- Rank 1 = best stock
- Top 20 stocks form recommendation list
