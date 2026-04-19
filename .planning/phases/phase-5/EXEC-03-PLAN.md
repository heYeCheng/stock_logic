---
plan_id: EXEC-03
phase: 5
requirement: EXEC-03
title: Stock Recommendation Markers
description: Implement recommendation marker classification (逻辑受益股/关联受益股/情绪跟风股)
type: feature
estimated_effort: 0.5h
---

# Plan: EXEC-03 - Stock Recommendation Markers

## Goal
Implement recommendation marker classification that explains the rationale behind each stock recommendation.

## Context
- Research: `.planning/phases/phase-5/RESEARCH.md` (EXEC-03 section)
- Models: `src/market/models.py`
- Dependencies: Phase 4 (logic_score, market_score, exposure_coefficient, catalyst_level)

## Marker Types

| Marker | Meaning | Criteria |
|--------|---------|----------|
| 逻辑受益股 | Logic beneficiary | High logic score + high exposure |
| 关联受益股 | Related beneficiary | Medium logic score + medium exposure |
| 情绪跟风股 | Sentiment follower | High market score + low logic score |

## Tasks

### Task 1: Create RecommendationMarker model
**File**: `src/market/models.py` (append)

```python
class RecommendationMarker(Base):
    """Stock recommendation marker and rationale."""
    __tablename__ = "recommendation_markers"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    marker = Column(String(50))  # 逻辑受益股/关联受益股/情绪跟风股
    marker_reason = Column(Text)  # Explanation of classification
    logic_score = Column(Numeric(7, 4))
    market_score = Column(Numeric(7, 4))
    exposure_coefficient = Column(Numeric(7, 4))
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create MarkerClassifier service
**File**: `src/market/marker.py` (create)

```python
from decimal import Decimal
from typing import Tuple

class MarkerClassifier:
    """Classify stock recommendation markers."""
    
    # Thresholds
    LOGIC_HIGH = Decimal("0.7")
    LOGIC_MEDIUM = Decimal("0.4")
    EXPOSURE_HIGH = Decimal("0.5")
    EXPOSURE_MEDIUM = Decimal("0.3")
    MARKET_HIGH = Decimal("0.6")
    
    def classify_marker(
        self,
        logic_score: Decimal,
        market_score: Decimal,
        exposure_coefficient: Decimal,
        catalyst_level: str
    ) -> Tuple[str, str]:
        """
        Classify recommendation marker.
        
        Returns:
            (marker, reason)
        """
        # Logic beneficiary: high logic score + high exposure
        if (logic_score >= self.LOGIC_HIGH and 
            exposure_coefficient >= self.EXPOSURE_HIGH):
            return (
                "逻辑受益股",
                f"高逻辑分 ({logic_score}) 且强暴露 ({exposure_coefficient})"
            )
        
        # Related beneficiary: medium logic score
        elif (logic_score >= self.LOGIC_MEDIUM and 
              exposure_coefficient >= self.EXPOSURE_MEDIUM):
            return (
                "关联受益股",
                f"中等逻辑分 ({logic_score}) 且中等暴露 ({exposure_coefficient})"
            )
        
        # Sentiment follower: high market score, low logic
        elif (market_score >= self.MARKET_HIGH and 
              logic_score < self.LOGIC_MEDIUM):
            return (
                "情绪跟风股",
                f"高市场分 ({market_score}) 但低逻辑分 ({logic_score})"
            )
        
        # Default based on logic score
        elif logic_score >= self.LOGIC_MEDIUM:
            return (
                "逻辑受益股",
                f"逻辑分 ({logic_score}) 支持"
            )
        else:
            return (
                "情绪跟风股",
                f"市场分 ({market_score}) 驱动"
            )
    
    def build_reason(
        self,
        marker: str,
        logic_score: Decimal,
        market_score: Decimal,
        exposure_coefficient: Decimal,
        catalyst_level: str
    ) -> str:
        """Build detailed reason string."""
        reasons = []
        
        # Logic component
        if logic_score >= self.LOGIC_HIGH:
            reasons.append(f"高逻辑分 ({logic_score})")
        elif logic_score >= self.LOGIC_MEDIUM:
            reasons.append(f"中等逻辑分 ({logic_score})")
        else:
            reasons.append(f"低逻辑分 ({logic_score})")
        
        # Market component
        if market_score >= self.MARKET_HIGH:
            reasons.append(f"高市场分 ({market_score})")
        
        # Exposure component
        if exposure_coefficient >= self.EXPOSURE_HIGH:
            reasons.append(f"强暴露 ({exposure_coefficient})")
        
        # Catalyst component
        if catalyst_level == "strong":
            reasons.append("强催化剂")
        elif catalyst_level == "medium":
            reasons.append("中等催化剂")
        
        return "，".join(reasons)
```

### Task 3: Create MarkerService
**File**: `src/market/marker.py` (append)

```python
class MarkerService:
    """Manage recommendation marker snapshots."""
    
    def __init__(self):
        self.classifier = MarkerClassifier()
    
    async def generate_markers(
        self,
        snapshot_date: date
    ) -> List[RecommendationMarker]:
        """Generate markers for all stocks."""
        
        # Get scores
        scores = await self._get_stock_scores(snapshot_date)
        
        markers = []
        
        for stock_code, data in scores.items():
            marker, reason = self.classifier.classify_marker(
                data["logic_score"],
                data["market_score"],
                data["exposure_coefficient"],
                data["catalyst_level"]
            )
            
            rec = RecommendationMarker(
                stock_code=stock_code,
                snapshot_date=snapshot_date,
                marker=marker,
                marker_reason=reason,
                logic_score=data["logic_score"],
                market_score=data["market_score"],
                exposure_coefficient=data["exposure_coefficient"],
            )
            
            markers.append(rec)
        
        # Persist
        await self._persist_batch(markers)
        return markers
    
    async def get_stock_marker(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> Optional[RecommendationMarker]:
        """Get marker for a specific stock."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(RecommendationMarker).where(
                    RecommendationMarker.stock_code == stock_code,
                    RecommendationMarker.snapshot_date == snapshot_date
                )
            )
            return result.scalar_one_or_none()
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_recommendation_markers.py` (create)

```python
def upgrade() -> None:
    op.create_table('recommendation_markers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('marker', sa.String(50), nullable=True),
        sa.Column('marker_reason', sa.Text(), nullable=True),
        sa.Column('logic_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('market_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('exposure_coefficient', sa.Numeric(7, 4), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'recommendation_markers', ['stock_code'])
    op.create_index('idx_date', 'recommendation_markers', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_marker.py`

Test cases:
- Logic beneficiary classification (high logic + high exposure)
- Related beneficiary classification (medium logic + medium exposure)
- Sentiment follower classification (high market + low logic)
- Boundary conditions (exactly at thresholds)
- Reason string generation
- Default classification fallback

## Success Criteria
- [ ] MarkerClassifier implements all classifications
- [ ] Reason strings are informative
- [ ] RecommendationMarker model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 4: STOCK-02 (exposure), STOCK-04 (logic score), STOCK-05 (market score), STOCK-06 (catalyst)

## Notes
- Markers help users understand recommendation rationale
- Chinese marker names for direct UI display
- Reason strings should be concise but informative
