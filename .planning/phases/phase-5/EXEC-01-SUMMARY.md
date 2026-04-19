---
phase: 5
plan: EXEC-01
subsystem: market
tags: [position-calculation, sigmoid, macro-overlay, sector-overlay]
dependency_graph:
  requires:
    - Phase 2: Macro multiplier (MACRO-02)
    - Phase 4: Composite scores (STOCK-08), Sector states (MARKET-02)
  provides:
    - EXEC-02: Trading constraints use position recommendations
    - EXEC-03: Stock recommendation markers
    - EXEC-04: Hold decisions
tech_stack:
  added:
    - PositionCalculator service with sigmoid scaling
  patterns:
    - Multi-overlay calculation (base → macro → sector)
    - Tier-based position classification
key_files:
  created:
    - src/market/position.py
    - tests/test_position.py
    - alembic/versions/20260419_235000_add_position_recommendations.py
  modified:
    - src/market/models.py
decisions:
  - Sigmoid function used for smooth 0-1 scaling (composite * 2 - 1 input mapping)
  - Position tiers in Chinese for UI display: 空仓/轻仓/中等/重仓/满仓
  - Sector state multipliers: weak=0.5, normal=1.0, overheated=0.7
  - Default sector state = normal if unavailable
metrics:
  duration_minutes: 45
  tests_added: 25
  tests_passed: 25
  migration_status: success
---

# Phase 5 Plan EXEC-01: Continuous Position Function Summary

## One-liner

PositionCalculator service with sigmoid-based position scaling, macro multiplier overlay, and sector state overlay producing 空仓/轻仓/中等/重仓/满仓 tier recommendations.

## Summary

**Objective:** Implement continuous position recommendation function that converts composite scores (0-1) into position percentages (0-100%) with macro and sector overlays.

## Implementation Details

### PositionRecommendation Model (Task 1)
- Created in `src/market/models.py`
- Stores composite_score, macro_multiplier, sector_state inputs
- Stores recommended_position (0.0000-1.0000) and position_tier output
- Unique constraint on (stock_code, snapshot_date)

### PositionCalculator Service (Task 2)
- Created in `src/market/position.py`
- **Sigmoid scaling:** `sigmoid(composite_score * 2 - 1)` maps 0-1 to smooth 0-1 output
- **Macro overlay:** `base_position * macro_multiplier` (0.5-1.5 range)
- **Sector overlay:** Apply state multipliers (weak=0.5, normal=1.0, overheated=0.7)
- **Tier mapping:** 空仓 (<10%), 轻仓 (10-30%), 中等 (30-60%), 重仓 (60-80%), 满仓 (≥80%)

### Alembic Migration (Task 3)
- Created `20260419_235000_add_position_recommendations.py`
- Fixed down_revision to merge multiple migration heads
- Successfully migrated to `20260419_235000 (head)`

### Unit Tests (Task 4)
- Created `tests/test_position.py` with 25 tests
- All tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing Text import in models.py**
- **Found during:** Task 4 (test execution)
- **Issue:** `RecommendationMarker` model used `Text` column type without importing it
- **Fix:** Added `Text` to sqlalchemy imports
- **Files modified:** `src/market/models.py`
- **Commit:** ba50968

**2. [Rule 3 - Blocking] Fixed migration down_revision chain**
- **Found during:** Task 3 (migration execution)
- **Issue:** Multiple head revisions present - migration chain had divergence
- **Fix:** Updated down_revision to merge `add_constraint_checks_table`, `20260419_233000`, `20260419_234500`
- **Files modified:** `alembic/versions/20260419_235000_add_position_recommendations.py`
- **Commit:** cd1812b

## Commits

| Commit | Description |
|--------|-------------|
| 40e60ab | feat(EXEC-01): add PositionRecommendation model and PositionCalculator service |
| a1b9b1e | feat(EXEC-01): add Alembic migration for position_recommendations table |
| ba50968 | fix(EXEC-01): add missing Text import and create unit tests |
| cd1812b | fix(EXEC-01): correct migration down_revision to merge all heads |

## Self-Check: PASSED

- [x] `src/market/models.py` - PositionRecommendation model exists
- [x] `src/market/position.py` - PositionCalculator service exists
- [x] `alembic/versions/20260419_235000_add_position_recommendations.py` - Migration exists
- [x] `tests/test_position.py` - 25 tests exist and pass
- [x] Migration `20260419_235000 (head)` applied successfully

## Success Criteria

- [x] PositionCalculator implements sigmoid scaling
- [x] Macro and sector overlays applied correctly
- [x] Position tiers (空仓/轻仓/中等/重仓/满仓) map correctly
- [x] PositionRecommendation model created
- [x] Migration runs successfully
- [x] Unit tests pass (25/25)
