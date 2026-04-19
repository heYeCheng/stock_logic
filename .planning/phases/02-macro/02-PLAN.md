---
plan_id: 02-02
phase: 2
requirement: MACRO-02
title: Monetary-Credit Quadrant Determination
status: pending
created: 2026-04-19
---

# Plan: Monetary-Credit Quadrant Determination

**Requirement:** MACRO-02 — 四象限判定（货币 - 信用框架）+ macro_multiplier 计算

**Dependencies:** Phase 1 (Database), Phase 2 Plan 01 (Five-Dimension Scoring)

---

## Goal

Implement monetary-credit quadrant determination that:
1. Classifies monetary condition (wide/neutral/tight) based on M2 YoY
2. Classifies credit condition (wide/neutral/tight) based on 社融 YoY
3. Maps to one of four quadrants
4. Computes `macro_multiplier` in range [0.85, 1.15]

---

## Tasks

### Task 1: Quadrant Analyzer

**File:** `src/macro/quadrant.py`

```python
from enum import Enum
from dataclasses import dataclass

class MonetaryCondition(Enum):
    WIDE = "wide"
    NEUTRAL = "neutral"
    TIGHT = "tight"

class CreditCondition(Enum):
    WIDE = "wide"
    NEUTRAL = "neutral"
    TIGHT = "tight"

class Quadrant(Enum):
    WIDE_WIDE = "wide-wide"       # Risk ON, cyclicals
    WIDE_TIGHT = "wide-tight"     # Defensive
    TIGHT_WIDE = "tight-wide"     # Selective
    TIGHT_TIGHT = "tight-tight"   # Risk OFF

@dataclass
class QuadrantResult:
    monetary_condition: MonetaryCondition
    credit_condition: CreditCondition
    quadrant: Quadrant
    macro_multiplier: float

class QuadrantAnalyzer:
    """Determine monetary-credit quadrant and compute multiplier."""
    
    # Configurable thresholds
    M2_WIDE_THRESHOLD = 10.0      # M2 YoY > 10% = wide
    M2_TIGHT_THRESHOLD = 8.0      # M2 YoY < 8% = tight
    SOCIAL_FIN_WIDE = 15.0        # 社融 YoY > 15% = wide
    SOCIAL_FIN_TIGHT = 10.0       # 社融 YoY < 10% = tight
    
    def determine_monetary_condition(self, m2_yoy: float) -> MonetaryCondition
    def determine_credit_condition(self, social_fin_yoy: float) -> CreditCondition
    def determine_quadrant(self, monetary: MonetaryCondition, 
                          credit: CreditCondition) -> Quadrant
    def compute_multiplier(self, quadrant: Quadrant, 
                          composite_score: float) -> float
    def analyze(self, m2_yoy: float, social_fin_yoy: float, 
                composite_score: float) -> QuadrantResult
```

---

### Task 2: Multiplier Logic

**Implementation:**

```python
def compute_multiplier(self, quadrant: Quadrant, composite_score: float) -> float:
    """
    Compute macro_multiplier from composite score.
    
    Formula: multiplier = 1.0 + (composite_score * 0.15)
    Bounds: [0.85, 1.15]
    
    Examples:
    - composite = +1.0 → multiplier = 1.15 (max risk-on)
    - composite = 0.0  → multiplier = 1.00 (neutral)
    - composite = -1.0 → multiplier = 0.85 (max risk-off)
    """
    multiplier = 1.0 + (composite_score * 0.15)
    return max(0.85, min(1.15, multiplier))
```

**Quadrant-specific guidance (for logging/debugging):**

| Quadrant | Typical Multiplier | Sector Preference |
|----------|-------------------|-------------------|
| wide-wide | 1.05-1.15 | Cyclicals, Growth |
| wide-tight | 1.00-1.05 | Defensive, Bonds |
| tight-wide | 0.95-1.00 | Quality, Value |
| tight-tight | 0.85-0.90 | Cash, Gold |

---

### Task 3: Database Integration

**File:** `src/db/models.py` (update `MacroSnapshot`)

Add columns:
```python
monetary_condition = Column(Enum(MonetaryCondition))
credit_condition = Column(Enum(CreditCondition))
quadrant = Column(Enum(Quadrant))
macro_multiplier = Column(Numeric(4, 3))  # 0.85 to 1.15
```

---

### Task 4: Service Integration

**File:** `src/macro/service.py` (update)

```python
class MacroService:
    async def compute_snapshot(self, snapshot_date: date) -> MacroSnapshot:
        # ... existing fetch and scoring ...
        
        # Add quadrant analysis
        analyzer = QuadrantAnalyzer()
        quadrant_result = analyzer.analyze(
            m2_yoy=indicators['m2_yoy'],
            social_fin_yoy=indicators['social_financing_yoy'],
            composite_score=scores['composite_score']
        )
        
        snapshot.monetary_condition = quadrant_result.monetary_condition
        snapshot.credit_condition = quadrant_result.credit_condition
        snapshot.quadrant = quadrant_result.quadrant
        snapshot.macro_multiplier = quadrant_result.macro_multiplier
        
        return snapshot
```

---

### Task 5: Unit Tests

**File:** `tests/macro/test_quadrant.py`

```python
def test_wide_wide_quadrant():
    analyzer = QuadrantAnalyzer()
    result = analyzer.analyze(m2_yoy=12.0, social_fin_yoy=18.0, composite_score=0.8)
    assert result.quadrant == Quadrant.WIDE_WIDE
    assert 1.10 <= result.macro_multiplier <= 1.15

def test_tight_tight_quadrant():
    analyzer = QuadrantAnalyzer()
    result = analyzer.analyze(m2_yoy=6.0, social_fin_yoy=8.0, composite_score=-0.8)
    assert result.quadrant == Quadrant.TIGHT_TIGHT
    assert 0.85 <= result.macro_multiplier <= 0.90

def test_neutral_thresholds():
    analyzer = QuadrantAnalyzer()
    result = analyzer.analyze(m2_yoy=9.0, social_fin_yoy=12.0, composite_score=0.0)
    assert result.monetary_condition == MonetaryCondition.NEUTRAL
    assert result.credit_condition == CreditCondition.NEUTRAL
    assert result.macro_multiplier == 1.00
```

---

## Verification

```bash
# Run tests
python -m pytest tests/macro/test_quadrant.py -v

# Manual verification
python -c "
from src.macro.quadrant import QuadrantAnalyzer

analyzer = QuadrantAnalyzer()

# Test case 1: Wide-wide (risk-on)
result = analyzer.analyze(m2_yoy=12.0, social_fin_yoy=18.0, composite_score=0.8)
print(f'Wide-wide: {result.quadrant}, multiplier={result.macro_multiplier}')

# Test case 2: Tight-tight (risk-off)
result = analyzer.analyze(m2_yoy=6.0, social_fin_yoy=8.0, composite_score=-0.8)
print(f'Tight-tight: {result.quadrant}, multiplier={result.macro_multiplier}')

# Test case 3: Neutral
result = analyzer.analyze(m2_yoy=9.0, social_fin_yoy=12.0, composite_score=0.0)
print(f'Neutral: {result.quadrant}, multiplier={result.macro_multiplier}')
"
```

---

## Definition of Done

- [ ] `QuadrantAnalyzer` class implemented
- [ ] Monetary/credit condition classification working
- [ ] Quadrant mapping correct
- [ ] `macro_multiplier` computed and bounded [0.85, 1.15]
- [ ] Database model updated
- [ ] Service integration complete
- [ ] Tests pass for all four quadrants

---

## Risks

| Risk | Mitigation |
|------|------------|
| Threshold values need tuning | Configurable, document rationale |
| Edge cases at boundaries | Clear documentation of threshold behavior |
| Multiplier impact unclear | Log multiplier with each recommendation |

---

*Plan created: 2026-04-19*
