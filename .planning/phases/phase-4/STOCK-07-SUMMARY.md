---
phase: 4
plan: STOCK-07
subsystem: market
tags:
  - dragon-leader
  - zhongjun
  - follower
  - role-identification
  - STOCK-07
dependency_graph:
  requires:
    - Phase 1: Stock data (daily quotes)
    - MARKET-05: Limit board data
  provides:
    - Stock leader role classification
    - Dragon/zhongjun/follower scores
  affects:
    - STOCK-08: Composite scoring
tech_stack:
  added:
    - StockLeaderRole model
    - LeaderIdentificationService
    - LeaderService
    - LeaderRole enum
patterns:
  - Role classification with thresholds
  - Confidence scoring
key_files:
  created:
    - src/market/leader.py (service implementation)
    - tests/test_leader.py (unit tests)
  modified:
    - src/market/models.py (added StockLeaderRole, LeaderRole)
    - alembic/versions/20260419_220000_bb13c7f87339_add_stock_leader_roles_table.py
decisions:
  - Dragon threshold set to 5.0 (weighted limit-ups + consecutive gains + first-limit bonus)
  - Zhongjun threshold set to 3.0 (market cap rank + volume stability + trend consistency)
  - Dragon takes priority over zhongjun when both scores exceed thresholds
  - Confidence capped at 1.0 for very high scores
metrics:
  duration: "Implementation already complete from prior work"
  completed_date: "2026-04-19"
  test_count: 21
  test_pass_rate: "100%"
---

# Phase 4 Plan STOCK-07: Dragon/Leader Identification Summary

## One-liner

Implemented dragon/zhongjun/follower stock role classification with score-based thresholds and confidence calculation.

## Implementation Summary

STOCK-07 identifies stock leadership roles within sectors:

- **Dragon leader (龙头)**: Aggressive leader with limit-ups, consecutive gains, first-to-limit bonus
- **Zhongjun (中军)**: Stable anchor with large market cap, high volume stability, consistent trend
- **Follower (跟风)**: Neither dragon nor zhongjun

## Files Created/Modified

### Models (src/market/models.py)

**LeaderRole Enum** (lines 164-168):
```python
class LeaderRole(PyEnum):
    dragon = "dragon"       # 龙头 - aggressive leader with limit-ups
    zhongjun = "zhongjun"   # 中军 - stable anchor with large cap
    follower = "follower"   # 跟风 - neither dragon nor zhongjun
```

**StockLeaderRole Model** (lines 171-207):
- `stock_code`, `sector_id`, `snapshot_date` - composite unique key
- `role` - dragon/zhongjun/follower
- `dragon_score`, `zhongjun_score` - classification scores
- `confidence` - role assignment confidence (0.0-1.0)

### Services (src/market/leader.py)

**LeaderIdentificationService**:
- `calculate_dragon_score(limit_up_count, consecutive_gains, is_first_limit)` → Decimal
- `calculate_zhongjun_score(market_cap_rank, volume_stability, trend_consistency, sector_stocks_count)` → Decimal
- `identify_role(dragon_score, zhongjun_score)` → (LeaderRole, Decimal, Decimal)
- `calculate_confidence(role, dragon_score, zhongjun_score)` → float

**LeaderService**:
- `generate_snapshot(sector_id, snapshot_date, stocks_data)` → List[StockLeaderRole]
- Batch persists leader role records

### Database Migration

**alembic/versions/20260419_220000_bb13c7f87339_add_stock_leader_roles_table.py**:
- Creates `stock_leader_roles` table with indexes on stock_code, sector_id, snapshot_date
- Unique constraint on (stock_code, sector_id, snapshot_date)

### Unit Tests (tests/test_leader.py)

21 test cases covering:
- Dragon score calculation (4 tests)
- Zhongjun score calculation (4 tests)
- Role identification (5 tests)
- Confidence calculation (5 tests)
- Integration tests (3 tests)

## Test Results

```
============================= 21 passed in 6.82s ==============================
```

All success criteria met:
- [x] LeaderIdentificationService calculates scores correctly
- [x] Role thresholds work as expected
- [x] StockLeaderRole model created
- [x] LeaderService generates snapshots
- [x] Migration exists and table created in database
- [x] Unit tests pass (21/21)

## Scoring Formulas

### Dragon Score
```
dragon_score = limit_up_count × 2 + consecutive_gains + (3 if is_first_limit else 0)
```

Threshold: ≥ 5.0 → dragon role

### Zhongjun Score
```
zhongjun_score = (rank_score × 3) + (volume_stability × 2) + (trend_consistency × 2)
where rank_score = (sector_stocks_count - market_cap_rank + 1) / sector_stocks_count
```

Threshold: ≥ 3.0 → zhongjun role

### Role Priority
1. Dragon (if dragon_score ≥ 5.0)
2. Zhongjun (if zhongjun_score ≥ 3.0)
3. Follower (default)

### Confidence Calculation
- Dragon: `(dragon_score - 5.0) / 5.0`, capped at 1.0
- Zhongjun: `(zhongjun_score - 3.0) / 3.0`, capped at 1.0
- Follower: `min(dragon_dist, zhongjun_dist) / 5.0`, capped at 1.0

## Deviations from Plan

None - implementation matches plan exactly.

## Known Stubs

None - all functionality implemented.

## Threat Flags

None identified - role classification is internal analysis, no external trust boundaries.

## Self-Check: PASSED

- [x] src/market/leader.py exists
- [x] tests/test_leader.py exists
- [x] StockLeaderRole model in src/market/models.py
- [x] stock_leader_roles table in database
- [x] All 21 unit tests pass
