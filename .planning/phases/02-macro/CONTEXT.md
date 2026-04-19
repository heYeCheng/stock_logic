# Phase 2: Macro Environment - Context & Decisions

**Phase:** 2  
**Created:** 2026-04-19  
**Status:** Ready for planning

---

## Prior Context Applied

### From Phase 1 (Infrastructure)
- ✅ Database layer with SQLAlchemy 2.0 async ready
- ✅ Data fetchers with failover (Tushare → Akshare → Efinance)
- ✅ APScheduler with CronTrigger (daily job at 15:30 CST)
- ✅ Structured JSON logging for monitoring

### From Project Requirements
- **MACRO-01**: 宏观五维度评分（流动性、增长、通胀成本、政策、全球）
- **MACRO-02**: 四象限判定（货币 - 信用框架）+ macro_multiplier 计算
- **MACRO-03**: 月度数据对齐与事件触发更新机制
- **MACRO-04**: 宏观数据不可用降级方案（macro_multiplier = 1.00）

---

## Gray Areas Discussed

### 1. Data Source Priority for Macro Indicators

**Decision:** Use existing fetcher failover pattern
- Tushare primary (if token configured) → `tushare_fetcher.py` macro methods
- Akshare fallback (free, no token) → `akshare_fetcher.py` macro methods
- Efinance tertiary → `efinance_fetcher.py` macro methods

**Rationale:** Consistent with Phase 1 architecture, graceful degradation already built-in.

---

### 2. Scoring Threshold Configuration

**Decision:** Configurable thresholds via YAML config file
```yaml
# config/macro_thresholds.yaml
liquidity:
  m2_yoy:
    wide: 10.0      # >10% = wide (+1)
    tight: 8.0      # <8% = tight (-1)
credit:
  social_financing_yoy:
    wide: 15.0      # >15% = wide (+1)
    tight: 10.0     # <10% = tight (-1)
```

**Rationale:** Thresholds need backtesting optimization; hard-coding would limit flexibility.

---

### 3. Macro Multiplier Bounds

**Decision:** `[0.85, 1.15]` range with linear interpolation
```python
macro_multiplier = 1.0 + (composite_score * 0.15)
macro_multiplier = max(0.85, min(1.15, macro_multiplier))
```

**Rationale:** 
- 0.85 = max risk-off (tight-tight quadrant)
- 1.15 = max risk-on (wide-wide quadrant)
- Linear scaling avoids step-function discontinuities

---

### 4. Update Frequency & Timing

**Decision:** Monthly refresh on 15th day at 16:00 CST
- Most macro data released 10-15 days after month-end
- 16:00 CST = after market close, avoids intraday volatility
- Graceful degradation: if data unavailable, use previous month + log warning

**Cron expression:** `0 16 15 * *` (15th of each month, 16:00)

**Event-triggered updates:** Deferred to Phase 3 (requires policy NLP)

---

### 5. Quadrant Determination Logic

**Decision:** Two-step process
```python
# Step 1: Determine monetary condition
if m2_yoy > threshold_wide:
    monetary = 'wide'
elif m2_yoy < threshold_tight:
    monetary = 'tight'
else:
    monetary = 'neutral'

# Step 2: Determine credit condition
if social_financing_yoy > threshold_wide:
    credit = 'wide'
elif social_financing_yoy < threshold_tight:
    credit = 'tight'
else:
    credit = 'neutral'

# Step 3: Map to quadrant
quadrant = f"{monetary}-{credit}"  # e.g., "wide-wide"
```

**Rationale:** Transparent, auditable logic. Easy to explain to users.

---

### 6. Degradation Strategy (MACRO-04)

**Decision:** Three-level degradation
1. **Partial data unavailable**: Use available data, impute missing from prior month
2. **All data unavailable**: Use prior month's snapshot, apply -0.1 decay to composite_score
3. **No prior snapshot**: `macro_multiplier = 1.00` (neutral, no adjustment)

**Rationale:** System never crashes due to missing macro data; always produces a result.

---

## Implementation Decisions

### Architecture

```
src/macro/
├── __init__.py
├── fetcher.py          # Macro data fetcher (Tushare/Akshare/Efinance)
├── scorer.py           # Five-dimension scoring logic
├── quadrant.py         # Monetary-credit quadrant determination
└── scheduler.py        # Monthly refresh scheduler integration
```

### Data Flow

```
1. Monthly cron trigger (15th, 16:00 CST)
       ↓
2. MacroFetcher.fetch_all_indicators()
       ↓
3. MacroScorer.score_dimensions(indicators)
       ↓
4. QuadrantAnalyzer.determine_quadrant(scores)
       ↓
5. MacroSnapshot saved to database
       ↓
6. macro_multiplier available for Phase 3-5 calculations
```

### Integration Points

- **Phase 1 Scheduler:** `src/scheduler/daily_job.py` → add monthly macro job
- **Phase 1 Database:** `src/db/models.py` → add `MacroSnapshot` model
- **Phase 1 Logging:** `src/logging/app_logger.py` → log macro scores, quadrant changes
- **Phase 3+ Logic Layer:** `macro_multiplier` applied to position sizing

---

## Deferred Items

| Item | Deferred To | Reason |
|------|-------------|--------|
| Event-triggered policy updates | Phase 3 | Requires NLP on policy statements |
| High-frequency liquidity proxies | Phase 3 | DR007, 票据利率 need real-time data |
| Global dimension deep dive | Phase 3 | Fed policy, DXY impact modeling |
| Backtesting framework | Phase 5 | Need full logic layer first |
| YAML config file | Phase 3 | Phase 2 uses Python constants |

---

## Success Criteria (Phase 2)

1. ✅ Five-dimension macro scores computed and logged monthly
2. ✅ Monetary-credit quadrant correctly identified
3. ✅ `macro_multiplier` persisted to database, available for downstream phases
4. ✅ System degrades gracefully when data unavailable
5. ✅ All macro data fetched via existing failover pattern

---

## Next Steps

1. **Plan creation:** Generate 4 PLAN.md files for MACRO-01 through MACRO-04
2. **Execution:** Run Phase 2 plans (parallel execution where possible)
3. **Verification:** Confirm macro_multiplier available for Phase 3

---

*Context document created: 2026-04-19*
