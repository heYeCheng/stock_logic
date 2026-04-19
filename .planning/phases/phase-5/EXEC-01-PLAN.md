---
plan_id: EXEC-01
phase: 5
requirement: EXEC-01
title: Continuous Position Function
description: Implement continuous position function with macro and sector overlays
type: feature
estimated_effort: 1h
---

# Plan: EXEC-01 - Continuous Position Function

## Goal
Implement continuous position recommendation function that converts composite scores into position percentages (0-100%).

## Context
- Research: `.planning/phases/phase-5/RESEARCH.md` (EXEC-01 section)
- Models: `src/market/models.py`
- Dependencies: Phase 2 (macro_multiplier), Phase 4 (composite_score, sector_state)

## Formula

```python
def calculate_position(
    composite_score: Decimal,      # 0-1 from STOCK-08
    macro_multiplier: Decimal,      # 0.5-1.5 from MACRO-02
    sector_state: SectorState,      # weak/normal/overheated
) -> Decimal:
    # Base position from composite score (sigmoid scaling)
    base_position = sigmoid(composite_score * 2 - 1)
    
    # Macro overlay
    macro_adjusted = base_position * macro_multiplier
    
    # Sector state overlay
    state_multiplier = {
        SectorState.weak: Decimal("0.5"),
        SectorState.normal: Decimal("1.0"),
        SectorState.overheated: Decimal("0.7"),
    }[sector_state]
    
    final_position = macro_adjusted * state_multiplier
    
    # Clamp to 0-1
    return max(Decimal("0"), min(Decimal("1"), final_position))
```

## Tasks

### Task 1: Create PositionRecommendation model
**File**: `src/market/models.py` (append)

```python
class PositionRecommendation(Base):
    """Daily position recommendation for a stock."""
    __tablename__ = "position_recommendations"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    composite_score = Column(Numeric(7, 4))
    macro_multiplier = Column(Numeric(5, 2), default=1.00)
    sector_state = Column(String(20))  # weak/normal/overheated
    recommended_position = Column(Numeric(7, 4))  # 0.0 - 1.0
    position_tier = Column(String(20))  # 空仓/轻仓/中等/重仓/满仓
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create PositionCalculator service
**File**: `src/market/position.py` (create)

```python
from decimal import Decimal
from typing import Dict, Tuple
from src.market.models import SectorState

class PositionCalculator:
    """Calculate continuous position recommendations."""
    
    # Position tier boundaries
    TIER_EMPTY = Decimal("0.10")    # 0-10%
    TIER_LIGHT = Decimal("0.30")    # 10-30%
    TIER_MODERATE = Decimal("0.60") # 30-60%
    TIER_HEAVY = Decimal("0.80")    # 60-80%
    # 80-100% = full
    
    # Sector state multipliers
    STATE_MULTIPLIERS = {
        SectorState.weak: Decimal("0.5"),
        SectorState.normal: Decimal("1.0"),
        SectorState.overheated: Decimal("0.7"),
    }
    
    def sigmoid(self, x: Decimal) -> Decimal:
        """Sigmoid function for smooth scaling."""
        import math
        return Decimal(str(1 / (1 + math.exp(-float(x))))
    
    def calculate_base_position(self, composite_score: Decimal) -> Decimal:
        """Calculate base position from composite score."""
        # Map 0-1 to sigmoid input
        sigmoid_input = composite_score * 2 - 1
        return self.sigmoid(sigmoid_input)
    
    def apply_macro_overlay(
        self,
        base_position: Decimal,
        macro_multiplier: Decimal
    ) -> Decimal:
        """Apply macro multiplier overlay."""
        return base_position * macro_multiplier
    
    def apply_sector_overlay(
        self,
        position: Decimal,
        sector_state: SectorState
    ) -> Decimal:
        """Apply sector state overlay."""
        multiplier = self.STATE_MULTIPLIERS.get(
            sector_state, Decimal("1.0")
        )
        return position * multiplier
    
    def calculate_position(
        self,
        composite_score: Decimal,
        macro_multiplier: Decimal,
        sector_state: SectorState
    ) -> Decimal:
        """
        Calculate full position recommendation.
        
        Returns:
            Position percentage (0.0 - 1.0)
        """
        base = self.calculate_base_position(composite_score)
        macro_adjusted = self.apply_macro_overlay(base, macro_multiplier)
        final = self.apply_sector_overlay(macro_adjusted, sector_state)
        
        # Clamp
        return max(Decimal("0"), min(Decimal("1"), final))
    
    def get_position_tier(self, position: Decimal) -> str:
        """Map position to tier name."""
        if position < self.TIER_EMPTY:
            return "空仓"
        elif position < self.TIER_LIGHT:
            return "轻仓"
        elif position < self.TIER_MODERATE:
            return "中等"
        elif position < self.TIER_HEAVY:
            return "重仓"
        else:
            return "满仓"
```

### Task 3: Create PositionService
**File**: `src/market/position.py` (append)

```python
class PositionService:
    """Manage position recommendation snapshots."""
    
    def __init__(self):
        self.calculator = PositionCalculator()
    
    async def generate_recommendations(
        self,
        snapshot_date: date
    ) -> List[PositionRecommendation]:
        """Generate position recommendations for all stocks."""
        
        # Get composite scores
        composites = await self._get_composite_scores(snapshot_date)
        
        # Get macro multiplier
        macro_mult = await self._get_macro_multiplier(snapshot_date)
        
        # Get sector states
        sector_states = await self._get_sector_states(snapshot_date)
        
        # Generate recommendations
        recommendations = []
        
        for stock_code, composite in composites.items():
            sector_state = sector_states.get(stock_code, SectorState.normal)
            
            position = self.calculator.calculate_position(
                composite, macro_mult, sector_state
            )
            
            tier = self.calculator.get_position_tier(position)
            
            rec = PositionRecommendation(
                stock_code=stock_code,
                snapshot_date=snapshot_date,
                composite_score=composite,
                macro_multiplier=macro_mult,
                sector_state=sector_state.value,
                recommended_position=position,
                position_tier=tier,
            )
            
            recommendations.append(rec)
        
        # Persist
        await self._persist_batch(recommendations)
        return recommendations
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_position_recommendations.py` (create)

```python
def upgrade() -> None:
    op.create_table('position_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('composite_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('macro_multiplier', sa.Numeric(5, 2), nullable=True),
        sa.Column('sector_state', sa.String(20), nullable=True),
        sa.Column('recommended_position', sa.Numeric(7, 4), nullable=True),
        sa.Column('position_tier', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'position_recommendations', ['stock_code'])
    op.create_index('idx_date', 'position_recommendations', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_position.py`

Test cases:
- Sigmoid function (boundary values)
- Base position calculation (0, 0.5, 1.0 composite)
- Macro overlay (various multipliers)
- Sector overlay (weak/normal/overheated)
- Position tier boundaries
- Full calculation integration

## Success Criteria
- [ ] PositionCalculator implements sigmoid scaling
- [ ] Macro and sector overlays applied correctly
- [ ] Position tiers map correctly
- [ ] PositionRecommendation model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 2: Macro multiplier (MACRO-02)
- Phase 4: Composite scores (STOCK-08), Sector states (MARKET-02)

## Notes
- Sigmoid provides smooth 0-1 transition
- Tier names in Chinese for UI display
- Default sector state = normal if unavailable
