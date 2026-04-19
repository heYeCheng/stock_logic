---
plan_id: 02-04
phase: 2
requirement: MACRO-04
title: Graceful Degradation Strategy
status: pending
created: 2026-04-19
---

# Plan: Graceful Degradation Strategy

**Requirement:** MACRO-04 — 宏观数据不可用降级方案（macro_multiplier = 1.00）

**Dependencies:** Phase 1 (Logging), Phase 2 Plan 01 (Five-Dimension Scoring)

---

## Goal

Implement graceful degradation that:
1. Handles partial data unavailability (some indicators missing)
2. Handles complete data unavailability (all indicators missing)
3. Handles missing prior snapshot (first run)
4. Always produces a valid `macro_multiplier` (never crashes)

---

## Tasks

### Task 1: Degradation Levels

**File:** `src/macro/service.py`

```python
from enum import Enum

class DegradationLevel(Enum):
    FULL = "full"           # All data available, normal operation
    PARTIAL = "partial"     # Some indicators missing, impute from prior
    LIMITED = "limited"     # All indicators missing, use prior + decay
    MINIMAL = "minimal"     # No prior snapshot, multiplier = 1.00

@dataclass
class DegradationResult:
    level: DegradationLevel
    macro_multiplier: float
    composite_score: Optional[float]
    reason: str
```

---

### Task 2: Degradation Logic

**File:** `src/macro/service.py`

```python
class MacroService:
    async def compute_snapshot(self, snapshot_date: date) -> MacroSnapshot:
        """
        Compute macro snapshot with graceful degradation.
        
        Degradation levels:
        1. FULL: All data available → normal scoring
        2. PARTIAL: Some indicators missing → impute from prior month
        3. LIMITED: All indicators missing → use prior + decay (-0.1)
        4. MINIMAL: No prior snapshot → multiplier = 1.00 (neutral)
        """
        # Step 1: Try to fetch all indicators
        fetcher = MacroFetcher()
        indicators = await fetcher.fetch_all()
        
        # Step 2: Determine degradation level
        degradation = self._assess_data_quality(indicators)
        
        if degradation == DegradationLevel.FULL:
            return await self._compute_full_snapshot(snapshot_date, indicators)
        
        elif degradation == DegradationLevel.PARTIAL:
            return await self._compute_partial_snapshot(snapshot_date, indicators)
        
        elif degradation == DegradationLevel.LIMITED:
            return await self._compute_limited_snapshot(snapshot_date)
        
        else:  # MINIMAL
            return await self._compute_minimal_snapshot(snapshot_date)
    
    def _assess_data_quality(self, indicators: dict) -> DegradationLevel:
        """Assess data quality and determine degradation level."""
        required_fields = ['m2_yoy', 'social_financing_yoy', 'cpi_yoy', 'ppi_yoy', 'pmi']
        
        available = sum(1 for f in required_fields if indicators.get(f) is not None)
        total = len(required_fields)
        
        if available == total:
            return DegradationLevel.FULL
        elif available >= total // 2:
            return DegradationLevel.PARTIAL
        elif available > 0:
            return DegradationLevel.LIMITED
        else:
            return DegradationLevel.MINIMAL
```

---

### Task 3: Partial Snapshot (Imputation)

**File:** `src/macro/service.py`

```python
async def _compute_partial_snapshot(self, snapshot_date: date, indicators: dict):
    """
    Compute snapshot with partial data.
    Impute missing indicators from prior month.
    """
    # Fetch prior snapshot
    prior = await self.get_latest_snapshot()
    
    if prior is None:
        # No prior snapshot → fall back to MINIMAL
        return await self._compute_minimal_snapshot(snapshot_date)
    
    # Impute missing fields from prior
    for key in ['m2_yoy', 'social_financing_yoy', 'cpi_yoy', 'ppi_yoy', 'pmi']:
        if indicators.get(key) is None:
            indicators[key] = getattr(prior, key, None)
    
    # Score with imputed data
    scorer = MacroScorer()
    scores = scorer.score_all(indicators)
    
    # Apply small penalty for imputation uncertainty
    scores['composite_score'] *= 0.95  # 5% uncertainty discount
    
    logger.warning(f"Macro snapshot computed with partial data (imputed from prior)")
    logger.warning(f"Composite score (adjusted): {scores['composite_score']}")
    
    # ... persist snapshot ...
```

---

### Task 4: Limited Snapshot (Prior + Decay)

**File:** `src/macro/service.py`

```python
async def _compute_limited_snapshot(self, snapshot_date: date):
    """
    Compute snapshot when all indicators unavailable.
    Use prior snapshot with natural decay.
    """
    prior = await self.get_latest_snapshot()
    
    if prior is None:
        # No prior snapshot → fall back to MINIMAL
        return await self._compute_minimal_snapshot(snapshot_date)
    
    # Apply decay to prior composite score
    decay_factor = 0.9  # 10% decay per month
    decayed_score = prior.composite_score * decay_factor
    
    logger.warning(f"Macro snapshot computed with decay (no fresh data)")
    logger.warning(f"Prior composite: {prior.composite_score}, decayed: {decayed_score}")
    
    # Compute multiplier from decayed score
    analyzer = QuadrantAnalyzer()
    multiplier = analyzer.compute_multiplier(decayed_score)
    
    # Create snapshot with prior quadrant (unchanged)
    snapshot = MacroSnapshot(
        snapshot_date=snapshot_date,
        composite_score=decayed_score,
        monetary_condition=prior.monetary_condition,
        credit_condition=prior.credit_condition,
        quadrant=prior.quadrant,
        macro_multiplier=multiplier,
        # ... other fields from prior ...
    )
    
    return snapshot
```

---

### Task 5: Minimal Snapshot (Neutral Default)

**File:** `src/macro/service.py`

```python
async def _compute_minimal_snapshot(self, snapshot_date: date):
    """
    Compute snapshot when no data and no prior snapshot available.
    Return neutral multiplier (1.00).
    """
    logger.warning("No macro data and no prior snapshot available")
    logger.warning("Using neutral macro_multiplier = 1.00")
    
    snapshot = MacroSnapshot(
        snapshot_date=snapshot_date,
        composite_score=0.0,
        monetary_condition=MonetaryCondition.NEUTRAL,
        credit_condition=CreditCondition.NEUTRAL,
        quadrant=Quadrant.WIDE_WIDE,  # Default, arbitrary
        macro_multiplier=1.00,
        # ... other fields NULL ...
    )
    
    return snapshot
```

---

### Task 6: Logging & Alerting

**File:** `src/macro/service.py`

```python
async def compute_snapshot(self, snapshot_date: date) -> MacroSnapshot:
    try:
        snapshot = await self._compute_snapshot_impl(snapshot_date)
        
        # Log degradation level
        if snapshot.degradation_level != DegradationLevel.FULL:
            logger.warning(f"Macro snapshot computed at {snapshot.degradation_level.value} degradation")
        
        return snapshot
        
    except Exception as e:
        # CRITICAL: Never crash, always return at least MINIMAL
        logger.error(f"Unexpected error in macro snapshot: {e}", exc_info=True)
        return await self._compute_minimal_snapshot(snapshot_date)
```

---

### Task 7: Unit Tests

**File:** `tests/macro/test_degradation.py`

```python
async def test_full_data_available():
    """Test normal operation with all data."""
    service = MacroService()
    # Mock fetcher to return all data
    snapshot = await service.compute_snapshot(date.today())
    assert snapshot.degradation_level == DegradationLevel.FULL
    assert snapshot.macro_multiplier is not None

async def test_partial_data_imputation():
    """Test partial data with imputation from prior."""
    service = MacroService()
    # Mock fetcher to return partial data
    snapshot = await service.compute_snapshot(date.today())
    assert snapshot.degradation_level == DegradationLevel.PARTIAL
    assert snapshot.composite_score < snapshot.prior_composite_score  # Penalty applied

async def test_no_prior_snapshot():
    """Test first run with no prior snapshot."""
    service = MacroService()
    # Mock fetcher to return no data, no prior
    snapshot = await service.compute_snapshot(date.today())
    assert snapshot.degradation_level == DegradationLevel.MINIMAL
    assert snapshot.macro_multiplier == 1.00
```

---

## Verification

```bash
# Run tests
python -m pytest tests/macro/test_degradation.py -v

# Manual verification (simulate no data)
python -c "
from src.macro.service import MacroService, DegradationLevel
from datetime import date
import asyncio

async def main():
    service = MacroService()
    
    # Test 1: Normal operation
    snapshot = await service.compute_snapshot(date.today())
    print(f'Degradation: {snapshot.degradation_level}')
    print(f'Multiplier: {snapshot.macro_multiplier}')

asyncio.run(main())
"
```

---

## Definition of Done

- [ ] Four degradation levels implemented
- [ ] Partial data imputation from prior month
- [ ] Decay applied when all data unavailable
- [ ] Neutral default (1.00) when no prior exists
- [ ] Never crashes, always produces valid multiplier
- [ ] Degradation level logged for monitoring
- [ ] Tests cover all degradation scenarios

---

## Risks

| Risk | Mitigation |
|------|------------|
| Silent degradation | Log warnings at each degradation level |
| Decay too aggressive | Configurable decay factor (default 0.9) |
| Imputation from stale prior | Limit imputation to 3 months max |

---

*Plan created: 2026-04-19*
