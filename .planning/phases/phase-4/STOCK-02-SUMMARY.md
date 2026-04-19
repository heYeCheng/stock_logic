---
phase: 4
plan: STOCK-02
subsystem: market, database
tags: [exposure, calculation, STOCK-02]
dependency_graph:
  requires: [STOCK-01, Phase3-logic-models]
  provides: [STOCK-03, STOCK-04, STOCK-08]
  affects: [src/market/exposure.py, src/market/models.py, alembic/versions/]
tech_stack:
  added: [ExposureCalculator, StockLogicExposure, ExposureQueries]
  patterns: [keyword overlap matching, batch calculation, async queries]
key_files:
  created: [src/market/exposure.py, tests/market/test_exposure.py, alembic/versions/20260419_223000_add_stock_logic_exposures.py]
  modified: [src/market/__init__.py, src/market/models.py, alembic/versions/*]
decisions:
  - "Migration chain aligned to single linear path to resolve multiple heads error"
  - "Exposure formula: max(affiliation_strength) × keyword_overlap_ratio"
metrics:
  duration: ~2h
  completed: "2026-04-19"
  tests: 17 passed
---

# Phase 4 Plan STOCK-02: Exposure Coefficient Calculation Summary

## One-liner
Implemented ExposureCalculator with keyword overlap matching algorithm and StockLogicExposure snapshot table for daily stock-logic exposure tracking.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ExposureCalculator | d8ca88f | src/market/exposure.py |
| 2 | Create Stock model with keywords | d8ca88f | src/market/models.py |
| 3 | Create query interface | d8ca88f | src/market/exposure.py |
| 4 | Create exposure snapshot table | d8ca88f | src/market/models.py |
| 5 | Create unit tests | d8ca88f | tests/market/test_exposure.py |
| 6 | Fix Alembic migration chain | d8ca88f | alembic/versions/*.py |

## Verification Results

**Unit tests:** 17/17 passed
- 9 single exposure calculation tests
- 4 batch exposure calculation tests  
- 4 async query method tests

**Migration:** Successfully upgraded to `add_stocks_table` (head)
- Migration chain: `bb13c7f87339` → `add_stock_logic_scores` → `add_stock_logic_exposures` → `add_sector_keywords` → `add_stock_composite_scores` → `add_stocks_table`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Alembic migration chain with multiple heads**
- **Found during:** Task 6 - Migration run
- **Issue:** Multiple migration files had conflicting `down_revision` values creating 3 separate branches instead of single linear chain
- **Fix:** Modified `down_revision` in migration files to create proper chain:
  - `20260419_220000_bb13c7f87339_add_stock_leader_roles_table.py`: `down_revision = 'add_stock_sector_mappings'`
  - `20260419_223000_add_stock_logic_exposures.py`: `down_revision = 'add_stock_logic_scores'`
  - `20260419_220000_add_stock_composite_scores.py`: `down_revision = 'add_sector_keywords'`
- **Files modified:** 3 migration files
- **Commit:** d8ca88f

**2. [Rule 3 - Blocking] Fixed migration file naming**
- **Issue:** Migration file named `20260419_223000_add_stock_logic_exposures_table.py` but referenced as `add_stock_logic_exposures` in chain
- **Fix:** Renamed file to match revision ID
- **Commit:** d8ca88f

## Key Files Created/Modified

### Created
- `src/market/exposure.py` - ExposureCalculator and ExposureQueries classes
- `tests/market/test_exposure.py` - 17 unit tests
- `alembic/versions/20260419_223000_add_stock_logic_exposures.py` - Migration for exposure table

### Modified
- `src/market/__init__.py` - Export new classes
- `src/market/models.py` - Added StockModel and StockLogicExposure models
- Multiple Alembic migration files for chain alignment

## Implementation Details

### Exposure Formula
```python
exposure = max_affiliation_strength × logic_match_score

where:
- max_affiliation_strength = max(mapping.affiliation_strength for all sector mappings)
- logic_match_score = keyword_overlap / len(logic_keywords)
- keyword_overlap = len(logic_keywords ∩ stock_keywords)
- Result capped at 1.0
```

### Database Schema
```sql
CREATE TABLE stock_logic_exposures (
    id INTEGER PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    logic_id VARCHAR(64) NOT NULL,
    snapshot_date DATE NOT NULL,
    exposure_coefficient NUMERIC(7, 4),  -- 0.0000 to 1.0000
    affiliation_strength NUMERIC(3, 2),   -- 0.00 to 1.00
    logic_match_score NUMERIC(7, 4),      -- 0.0000 to 1.0000
    UNIQUE(stock_code, logic_id, snapshot_date)
);
```

## Self-Check: PASSED

- [x] All 17 tests pass
- [x] Migration runs successfully (`alembic upgrade head`)
- [x] StockLogicExposure model created
- [x] ExposureCalculator implements correct formula
- [x] Migration chain has single head
