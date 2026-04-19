---
plan_id: STOCK-04
phase: 4
requirement: STOCK-04
title: Stock Logic Score
description: Calculate individual stock logic score from exposure-weighted logic scores
type: feature
estimated_effort: 1h
---

# Plan: STOCK-04 - Stock Logic Score

## Goal
Implement stock logic score calculation that aggregates logic scores weighted by exposure coefficients.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-04 section)
- Models: src/market/models.py, src/logic/models.py
- Dependencies: STOCK-02 (exposure), Phase 3 (logic scores)

## Formula

```python
def calculate_stock_logic_score(stock, logic_scores, exposure_map):
    """
    stock: StockModel
    logic_scores: Dict[logic_id, LogicScore]
    exposure_map: Dict[logic_id, exposure_coefficient]
    
    Returns:
        stock_logic_score (0-1)
    """
    
    total_weighted_score = Decimal("0")
    total_exposure = Decimal("0")
    
    for logic_id, score in logic_scores.items():
        exposure = exposure_map.get(logic_id, Decimal("0"))
        
        if exposure > 0:
            # Weight by exposure
            total_weighted_score += score.decayed_score * exposure
            total_exposure += exposure
    
    if total_exposure == 0:
        return Decimal("0")
    
    # Normalize by total exposure
    stock_logic_score = total_weighted_score / total_exposure
    
    return min(stock_logic_score, Decimal("1.0"))
```

## Tasks

### Task 1: Create StockLogicScoreCalculator
**File**: `src/market/stock_logic.py` (create)

```python
from decimal import Decimal
from typing import Dict, List, Optional

class StockLogicScoreCalculator:
    """Calculate stock logic scores from exposure-weighted logic scores."""
    
    def calculate(
        self,
        logic_scores: Dict[str, LogicScore],
        exposures: Dict[str, Decimal]
    ) -> Decimal:
        """
        Calculate stock logic score.
        
        Args:
            logic_scores: Dict[logic_id, LogicScore]
            exposures: Dict[logic_id, exposure_coefficient]
        
        Returns:
            stock_logic_score (0-1)
        """
        total_weighted = Decimal("0")
        total_exposure = Decimal("0")
        
        for logic_id, score in logic_scores.items():
            exposure = exposures.get(logic_id, Decimal("0"))
            
            if exposure > 0 and score.decayed_score:
                total_weighted += score.decayed_score * exposure
                total_exposure += exposure
        
        if total_exposure == 0:
            return Decimal("0")
        
        result = total_weighted / total_exposure
        return min(result, Decimal("1.0"))
    
    def calculate_with_breakdown(
        self,
        logic_scores: Dict[str, LogicScore],
        exposures: Dict[str, Decimal]
    ) -> "StockLogicBreakdown":
        """
        Calculate score with detailed breakdown.
        
        Returns:
            StockLogicBreakdown with per-logic contributions
        """
        contributions = []
        total_weighted = Decimal("0")
        total_exposure = Decimal("0")
        
        for logic_id, score in logic_scores.items():
            exposure = exposures.get(logic_id, Decimal("0"))
            
            if exposure > 0 and score.decayed_score:
                contribution = score.decayed_score * exposure
                contributions.append({
                    "logic_id": logic_id,
                    "logic_score": score.decayed_score,
                    "exposure": exposure,
                    "contribution": contribution
                })
                total_weighted += contribution
                total_exposure += exposure
        
        final_score = Decimal("0") if total_exposure == 0 else min(
            total_weighted / total_exposure, Decimal("1.0")
        )
        
        return StockLogicBreakdown(
            final_score=final_score,
            total_exposure=total_exposure,
            contributions=contributions
        )
```

### Task 2: Create StockLogicScore model
**File**: `src/market/models.py` (append)

```python
class StockLogicScore(Base):
    """Daily stock logic score snapshot."""
    __tablename__ = "stock_logic_scores"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    logic_score = Column(Numeric(7, 4))  # 0-1
    total_exposure = Column(Numeric(7, 4))  # Sum of exposures
    contributing_logics = Column(Integer)  # Count of logics with exposure > 0
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 3: Create StockLogicService
**File**: `src/market/stock_logic.py` (append)

```python
class StockLogicService:
    """Manage stock logic score generation."""
    
    def __init__(self):
        self.calculator = StockLogicScoreCalculator()
    
    async def generate_snapshot(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> StockLogicScore:
        """Generate logic score snapshot for a stock."""
        
        # Get logic scores for date
        logic_scores = await self._get_logic_scores(snapshot_date)
        
        # Get stock exposures
        exposures = await self._get_stock_exposures(stock_code, snapshot_date)
        
        # Calculate score
        score = self.calculator.calculate(logic_scores, exposures)
        
        # Count contributing logics
        contributing = sum(1 for e in exposures.values() if e > 0)
        
        # Persist
        snapshot = StockLogicScore(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            logic_score=score,
            total_exposure=sum(exposures.values()),
            contributing_logics=contributing
        )
        
        await self._persist(snapshot)
        return snapshot
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_logic_scores.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_logic_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('total_exposure', sa.Numeric(7, 4), nullable=True),
        sa.Column('contributing_logics', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'stock_logic_scores', ['stock_code'])
    op.create_index('idx_date', 'stock_logic_scores', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_stock_logic.py`

Test cases:
- Score calculation (single logic)
- Score calculation (multiple logics)
- Score calculation (no exposure)
- Score capping at 1.0
- Breakdown generation
- Snapshot persistence

## Success Criteria
- [ ] StockLogicScoreCalculator works correctly
- [ ] StockLogicScore model created
- [ ] StockLogicService generates snapshots
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- STOCK-02: Exposure calculation (completed)
- Phase 3: Logic scores (completed)

## Notes
- Score normalized to 0-1
- Contributing logics count helps assess reliability
- Cached daily for performance
