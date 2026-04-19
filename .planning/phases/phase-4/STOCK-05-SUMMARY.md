---
phase: 4
plan: STOCK-05
subsystem: market-layer
tags: [stock-radar, technical-analysis, sentiment-analysis]
dependency_graph:
  requires: [INFRA-01, Phase 1 daily quotes]
  provides: [STOCK-06, STOCK-07, STOCK-08]
  affects: [stock_composite_scores]
tech_stack:
  added:
    - StockTechnicalCalculator (MA, volume, RSI, MACD)
    - StockSentimentCalculator (limit-ups, dragon, flow)
    - StockRadarService
  patterns:
    - Score-based evaluation
    - Multi-factor composite
key_files:
  created:
    - src/market/stock_radar.py
    - tests/test_stock_radar.py
    - alembic/versions/20260419_230000_add_stock_market_scores.py
  modified: []
decisions:
  - Used equal weights (50/50) for technical and sentiment composite
  - Technical weights: MA (0.3), Volume (0.25), RSI (0.25), MACD (0.2)
  - Sentiment weights: Limit-ups (0.4), Dragon (0.35), Flow (0.25)
metrics:
  duration: 0.5h
  completed: 2026-04-19
---

# Phase 4 Plan STOCK-05: Stock Market Radar Summary

## One-liner

Individual stock market radar with technical indicators (MA alignment, volume, RSI, MACD) and sentiment indicators (limit-ups, dragon status, institutional flow).

---

## Implementation Summary

### Task 1: Create StockMarketScore model ✅

**File**: `src/market/models.py` (already exists from prior plan)

Model already created with:
- `stock_code`, `snapshot_date` (unique constraint)
- `technical_score`, `sentiment_score`, `market_composite` (Numeric 7,4)
- Indexes on stock_code and snapshot_date

### Task 2: Implement StockTechnicalCalculator ✅

**File**: `src/market/stock_radar.py`

Technical indicators implemented:
- **MA alignment** (weight 0.3): Price vs MA5/MA10/MA20, scores 1.0 for bullish, 0 for bearish
- **Volume trend** (weight 0.25): 5-day avg vs 20-day avg ratio
- **RSI** (weight 0.25): 14-day RSI mapped to 0-1 score
- **MACD** (weight 0.2): Signal line crossover detection

### Task 3: Implement StockSentimentCalculator ✅

**File**: `src/market/stock_radar.py`

Sentiment indicators implemented:
- **Limit-up frequency** (weight 0.4): Count in past 5 days / 5
- **Dragon leader status** (weight 0.35): Binary 1.0/0.5
- **Institutional flow** (weight 0.25): Normalized to 1M threshold

### Task 4: Create StockRadarService ✅

**File**: `src/market/stock_radar.py`

Service features:
- `generate_snapshot()` method for daily score generation
- Composite score = (technical + sentiment) / 2
- Upsert logic for database persistence

### Task 5: Create Alembic migration ✅

**File**: `alembic/versions/20260419_230000_add_stock_market_scores.py`

Migration executed successfully.

### Task 6: Create unit tests ✅

**File**: `tests/test_stock_radar.py`

Test coverage:
- Technical: MA alignment (bullish/bearish), volume trend, RSI, MACD
- Sentiment: limit-ups, dragon status, institutional flow combinations
- Service: snapshot generation
- Data class: daily return calculation

**Test results**: 20/20 passed

---

## Deviations from Plan

### Auto-fixed Issues

**None** - Implementation followed plan exactly.

### Plan Adjustments

**None** - All tasks completed as specified.

---

## Known Stubs

None - All functionality fully implemented.

---

## Threat Flags

None - Stock market radar uses only volume-price data, no new security surface introduced.

---

## Success Criteria Verification

- [x] StockTechnicalCalculator implements all indicators (MA, volume, RSI, MACD)
- [x] StockSentimentCalculator works (limit-ups, dragon, flow)
- [x] StockRadarService generates snapshots
- [x] StockMarketScore model created (already existed)
- [x] Migration runs successfully
- [x] Unit tests pass (20/20)

---

## Self-Check: PASSED

All created files verified, commit hash recorded.

---

## Execution Metrics

- **Duration**: 0.5 hours
- **Files created**: 3
- **Tests**: 20 passing
- **Migration status**: Applied successfully
