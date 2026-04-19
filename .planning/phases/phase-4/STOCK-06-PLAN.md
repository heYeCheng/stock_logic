---
plan_id: STOCK-06
phase: 4
requirement: STOCK-06
title: Catalyst Markers
description: Implement catalyst classification (strong/medium/none)
type: feature
estimated_effort: 0.5h
---

# Plan: STOCK-06 - Catalyst Markers

## Goal
Implement simplified catalyst markers (strong/medium/none) based on recent high-importance events.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-06 section)
- Models: src/market/models.py
- Dependencies: Phase 3 (events)

## Classification Logic

```python
def determine_catalyst(stock, recent_events):
    """
    stock: StockModel
    recent_events: List of recent logic events affecting this stock
    
    Returns:
        "strong" | "medium" | "none"
    """
    
    if not recent_events:
        return "none"
    
    # Count high-importance events
    high_importance_count = sum(
        1 for e in recent_events if e.importance_level == "high"
    )
    
    if high_importance_count >= 2:
        return "strong"
    elif high_importance_count == 1:
        return "medium"
    else:
        return "none"
```

## Tasks

### Task 1: Create CatalystMarker model
**File**: `src/market/models.py` (append)

```python
class StockCatalyst(Base):
    """Stock catalyst marker."""
    __tablename__ = "stock_catalysts"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    catalyst_level = Column(String(20))  # strong/medium/none
    event_count = Column(Integer)  # Count of recent events
    high_importance_count = Column(Integer)
    description = Column(Text)  # Brief description of catalyst
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create CatalystService
**File**: `src/market/catalyst.py` (create)

```python
from typing import List, Optional
from datetime import date, timedelta

class CatalystService:
    """Determine stock catalyst markers."""
    
    LOOKBACK_DAYS = 5  # Look back 5 days for events
    
    def determine_catalyst(
        self,
        events: List[EventModel]
    ) -> str:
        """
        Determine catalyst level from events.
        
        Args:
            events: Recent events affecting this stock
        
        Returns:
            "strong" | "medium" | "none"
        """
        if not events:
            return "none"
        
        # Count high-importance events
        high_count = sum(
            1 for e in events if e.importance_level == "high"
        )
        
        if high_count >= 2:
            return "strong"
        elif high_count == 1:
            return "medium"
        else:
            return "none"
    
    async def generate_catalyst(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> StockCatalyst:
        """Generate catalyst marker for a stock."""
        
        # Get recent events
        start_date = snapshot_date - timedelta(days=self.LOOKBACK_DAYS)
        events = await self._get_stock_events(stock_code, start_date, snapshot_date)
        
        # Determine catalyst
        catalyst = self.determine_catalyst(events)
        
        # Count events
        high_count = sum(1 for e in events if e.importance_level == "high")
        
        # Build description
        description = self._build_description(events, catalyst)
        
        # Persist
        record = StockCatalyst(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            catalyst_level=catalyst,
            event_count=len(events),
            high_importance_count=high_count,
            description=description
        )
        
        await self._persist(record)
        return record
    
    def _build_description(
        self,
        events: List[EventModel],
        catalyst: str
    ) -> str:
        """Build brief catalyst description."""
        if catalyst == "none":
            return "无显著催化剂"
        
        # Get unique logic names
        logic_names = list(set(e.logic_name for e in events if e.logic_name))
        
        if catalyst == "strong":
            return f"多重高重要性事件驱动：{', '.join(logic_names[:3])}"
        else:
            return f"重要事件驱动：{', '.join(logic_names[:3])}"
```

### Task 3: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_catalysts.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_catalysts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('catalyst_level', sa.String(20), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=True),
        sa.Column('high_importance_count', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'stock_catalysts', ['stock_code'])
    op.create_index('idx_date', 'stock_catalysts', ['snapshot_date'])
```

### Task 4: Create unit tests
**File**: `tests/test_catalyst.py`

Test cases:
- Catalyst determination (no events = none)
- Catalyst determination (1 high = medium)
- Catalyst determination (2+ high = strong)
- Event lookback window
- Description generation

## Success Criteria
- [ ] CatalystService determines markers correctly
- [ ] StockCatalyst model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 3: Event models (completed)

## Notes
- Simple classification based on high-importance count
- 5-day lookback window
- Description helps downstream UI display
