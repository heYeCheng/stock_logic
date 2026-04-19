---
plan_id: 02-01
phase: 2
requirement: MACRO-01
title: Macro Five-Dimension Scoring Module
status: pending
created: 2026-04-19
---

# Plan: Macro Five-Dimension Scoring Module

**Requirement:** MACRO-01 — 宏观五维度评分（流动性、增长、通胀成本、政策、全球）

**Dependencies:** Phase 1 (Database, Data Fetchers, Scheduler, Logging)

---

## Goal

Implement five-dimension macro scoring module that:
1. Fetches macro indicators from data sources (M2, 社融，CPI, PPI, PMI, etc.)
2. Scores each dimension from -1.0 to +1.0
3. Computes composite macro score
4. Persists snapshot to database

---

## Tasks

### Task 1: Database Model

**File:** `src/db/models.py`

Add `MacroSnapshot` model:
```python
class MacroSnapshot(Base):
    __tablename__ = "macro_snapshot"
    
    id = Column(Integer, primary_key=True)
    snapshot_date = Column(Date, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Liquidity dimension
    m2_yoy = Column(Numeric(5, 2))
    dr007_avg = Column(Numeric(5, 4))
    bond_10y_yield = Column(Numeric(5, 4))
    liquidity_score = Column(Numeric(3, 2))
    
    # Growth dimension
    gdp_yoy = Column(Numeric(5, 2))
    pmi_manufacturing = Column(Numeric(5, 2))
    industrial_prod_yoy = Column(Numeric(5, 2))
    growth_score = Column(Numeric(3, 2))
    
    # Inflation dimension
    cpi_yoy = Column(Numeric(5, 2))
    ppi_yoy = Column(Numeric(5, 2))
    inflation_score = Column(Numeric(3, 2))
    
    # Policy dimension
    policy_score = Column(Numeric(3, 2))
    
    # Global dimension
    fed_rate = Column(Numeric(5, 4))
    dxy_index = Column(Numeric(6, 2))
    us_cn_spread = Column(Numeric(5, 4))
    global_score = Column(Numeric(3, 2))
    
    # Composite
    composite_score = Column(Numeric(3, 2))
```

---

### Task 2: Macro Data Fetcher

**File:** `src/macro/fetcher.py`

```python
class MacroFetcher:
    """Fetch macro indicators from Tushare/Akshare/Efinance."""
    
    async def fetch_liquidity_indicators(self) -> dict
    async def fetch_growth_indicators(self) -> dict
    async def fetch_inflation_indicators(self) -> dict
    async def fetch_policy_indicators(self) -> dict
    async def fetch_global_indicators(self) -> dict
    async def fetch_all(self) -> dict
```

**Implementation notes:**
- Use existing fetcher failover pattern (Tushare → Akshare → Efinance)
- Return dict with raw indicator values (no scoring yet)
- Handle missing data gracefully (return None, don't raise)

---

### Task 3: Scoring Logic

**File:** `src/macro/scorer.py`

```python
class MacroScorer:
    """Score macro dimensions from -1.0 to +1.0."""
    
    # Configurable thresholds
    LIQUIDITY_WIDE = 10.0   # M2 YoY > 10% = +1
    LIQUIDITY_TIGHT = 8.0   # M2 YoY < 8% = -1
    CREDIT_WIDE = 15.0      # 社融 YoY > 15% = +1
    CREDIT_TIGHT = 10.0     # 社融 YoY < 10% = -1
    
    def score_liquidity(self, m2_yoy: float, dr007: float) -> float
    def score_growth(self, gdp_yoy: float, pmi: float) -> float
    def score_inflation(self, cpi_yoy: float, ppi_yoy: float) -> float
    def score_policy(self, fiscal_stance: str, monetary_stance: str) -> float
    def score_global(self, fed_rate: float, dxy: float) -> float
    def compute_composite(self, scores: dict) -> float
```

**Scoring logic:**
- Linear interpolation between thresholds
- Bounds: [-1.0, +1.0]
- Equal weight (0.2) for each dimension

---

### Task 4: Database Service

**File:** `src/macro/service.py`

```python
class MacroService:
    """Orchestrate macro scoring and persistence."""
    
    async def compute_snapshot(self, snapshot_date: date) -> MacroSnapshot
    async def get_latest_snapshot(self) -> Optional[MacroSnapshot]
    async def get_snapshot_by_date(self, date: date) -> Optional[MacroSnapshot]
```

---

### Task 5: Integration Test

**File:** `tests/macro/test_scorer.py`

```python
async def test_five_dimension_scoring():
    fetcher = MacroFetcher()
    scorer = MacroScorer()
    indicators = await fetcher.fetch_all()
    scores = scorer.score_all(indicators)
    assert -1.0 <= scores['liquidity_score'] <= 1.0
    assert -1.0 <= scores['composite_score'] <= 1.0
```

---

## Verification

```bash
# Run test
python -m pytest tests/macro/test_scorer.py -v

# Manual verification
python -c "
from src.macro.service import MacroService
from datetime import date
import asyncio

async def main():
    service = MacroService()
    snapshot = await service.compute_snapshot(date.today())
    print(f'Composite score: {snapshot.composite_score}')
    print(f'Liquidity: {snapshot.liquidity_score}')
    print(f'Growth: {snapshot.growth_score}')

asyncio.run(main())
"
```

---

## Definition of Done

- [ ] `MacroSnapshot` model created and migrated
- [ ] `MacroFetcher` fetches all indicators with failover
- [ ] `MacroScorer` scores all 5 dimensions
- [ ] `MacroService` orchestrates and persists snapshots
- [ ] Tests pass
- [ ] Logs show scores for each dimension

---

## Risks

| Risk | Mitigation |
|------|------------|
| Macro data unavailable | Graceful degradation, use prior month |
| Thresholds need tuning | Configurable, document defaults |
| Tushare rate limiting | Reuse Phase 1 rate limiter |

---

*Plan created: 2026-04-19*
