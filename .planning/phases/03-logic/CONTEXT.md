# Phase 3: Logic Layer - Context & Decisions

**Phase:** 3  
**Created:** 2026-04-19  
**Status:** Ready for planning

---

## Prior Context Applied

### From Phase 1 (Infrastructure)
- ✅ Database layer with SQLAlchemy 2.0 async + Alembic migrations
- ✅ Data fetchers with failover (Tushare → Akshare → Efinance)
- ✅ APScheduler with CronTrigger for daily/monthly jobs
- ✅ Structured JSON logging for monitoring
- ✅ LiteLLM integration ready for LLM calls

### From Phase 2 (Macro Environment)
- ✅ Macro five-dimension scoring complete
- ✅ Monetary-credit quadrant determination
- ✅ `macro_multiplier` available in database
- ✅ Graceful degradation pattern established

### From Project Requirements
- **LOGIC-01**: LLM 逻辑识别与归类（logic_id, direction, logic_family, importance_level）
- **LOGIC-02**: LLM 事件提取（两阶段 pipeline）
- **LOGIC-03**: 事件计分板规则引擎（加减分、自然衰减、有效期）
- **LOGIC-04**: 事件去重与指纹校验
- **LOGIC-05**: 净推力计算 + 反向逻辑标记
- **LOGIC-06**: LLM 降级策略（服务不可用则沿用上一日 + 衰减）

---

## Gray Areas Discussed

### 1. Logic Family Taxonomy

**Decision:** Start with 5 core families, extensible
```python
LOGIC_FAMILIES = {
    "technology": "技术突破、国产替代、研发进展",
    "policy": "国家政策、行业监管、税收优惠",
    "earnings": "财报超预期、盈利预警、分红回购",
    "m_a": "并购重组、股权激励、定增",
    "supply_chain": "供应链变化、大客户订单、原材料价格"
}
```

**Rationale:** 5 families cover 80%+ of A-stock catalyst events. Can extend later without breaking schema.

---

### 2. Two-Stage Pipeline Design

**Decision:** Strict separation between logic identification and event extraction

```
Stage 1: Logic Identification (one-time per news source)
  Input: News corpus
  Output: Logic schema (logic_id, family, direction, importance)

Stage 2: Event Extraction (daily batch)
  Input: Daily news + Logic schema
  Output: Events mapped to logic_ids
```

**Rationale:**
- Logic schema is relatively stable (weekly refresh)
- Events are daily flow
- Separation enables backtesting (re-extract events with same schema)

---

### 3. Scoring Rules Configuration

**Decision:** YAML configuration for scoring parameters

```yaml
# config/logic_scorecard.yaml
scoring:
  importance_multipliers:
    high: 1.5
    medium: 1.0
    low: 0.5
  
  decay:
    daily_rate: 0.95      # 5% daily decay
    half_life_days: 14    # ~14 days to 50%
  
  validity:
    default_days: 30
    technology: 45        # Tech logics last longer
    policy: 60            # Policy logics last longest
  
  thresholds:
    confidence_min: 0.6   # Reject LLM confidence < 0.6
    strength_min: 0.1     # Ignore very weak events
```

**Rationale:** Thresholds need backtesting optimization; hard-coding limits flexibility.

---

### 4. Event Fingerprint Design

**Decision:** SHA256 hash of canonical fields

```python
fingerprint = sha256(f"{source}:{event_date}:{logic_id}:{headline[:50]}")
```

**Components:**
1. `source`: News source (e.g., "sina", "eastmoney")
2. `event_date`: YYYY-MM-DD format
3. `logic_id`: Associated logic
4. `headline[:50]`: First 50 chars (captures variation)

**Deduplication window:** 24 hours

**Rationale:** Simple, deterministic, handles cross-source duplicates.

---

### 5. Net Thrust Calculation

**Decision:** Gross positive minus gross negative, with anti-logic flag

```python
def calculate_net_thrust(events: List[Event]) -> Tuple[float, bool]:
    positive_sum = sum(e.strength_adjusted for e in events if e.direction == 'positive')
    negative_sum = sum(e.strength_adjusted for e in events if e.direction == 'negative')
    
    net_thrust = positive_sum - negative_sum
    has_anti_logic = (positive_sum > 0 and negative_sum > 0)
    
    return net_thrust, has_anti_logic
```

**Rationale:** 
- Net thrust = directional signal strength
- Anti-logic flag = warning that signal is contested (human review may be needed)

---

### 6. LLM Degradation Strategy

**Decision:** Three-level degradation

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | LLM API responsive | Normal processing |
| **Degraded** | Slow responses, rate limits | Queue + batch, reduce model size |
| **Offline** | API unavailable | Use prior day scores × 0.9 decay |

**Fallback logic:**
```python
if llm_available:
    scores = await llm_process_today()
else:
    prior_scores = await db.get_yesterday_scores()
    scores = {k: v * 0.9 for k, v in prior_scores.items()}
    logger.warning("LLM offline, using decayed prior scores")
```

**Rationale:** System never crashes; always produces output even with LLM downtime.

---

### 7. Database Schema

**Decision:** Three core tables

```
logics          events          logic_scores
─────────       ───────         ──────────────
logic_id        event_id        logic_id (FK)
logic_family    logic_id (FK)   snapshot_date
direction       event_date      raw_score
importance      headline        decayed_score
keywords        strength_raw    net_thrust
validity_days   direction       has_anti_logic
                fingerprint     event_count
                is_expired      llm_status
```

**Rationale:** Normalized design, efficient queries by logic_id + date.

---

### 8. Integration with Macro Layer

**Decision:** `macro_multiplier` applies at execution layer, not logic layer

```
Logic Layer Output: net_thrust per logic_id
                    ↓
Macro Layer Output: macro_multiplier (from Phase 2)
                    ↓
Execution Layer:    position = f(net_thrust, macro_multiplier)
```

**Rationale:** Logic scores should be pure (macro-independent). Macro adjustment happens at position sizing.

---

## Implementation Decisions

### Architecture

```
src/logic/
├── __init__.py
├── models.py             # ORM models for logics, events, scores
├── llm_service.py        # LLM prompts, parsing, rate limiting
├── scorecard.py          # Event scorecard rule engine
├── fingerprint.py        # Deduplication logic
├── net_thrust.py         # Aggregation + anti-logic flagging
└── scheduler.py          # Daily batch job integration
```

### Data Flow

```
1. Daily cron trigger (15:30 CST, post-market)
       ↓
2. Fetch news from sources (Tushare/Akshare/Efinance)
       ↓
3. Stage 1: LLM identifies logics → logics table
       ↓
4. Stage 2: LLM extracts events → events table (with fingerprint check)
       ↓
5. Scorecard applies rules (加减分，decay, validity)
       ↓
6. Net thrust calculated → logic_scores table
       ↓
7. Logged for monitoring
```

### LLM Provider

**Decision:** Use LiteLLM abstraction (already in Phase 1)

```python
from litellm import acompletion

async def call_llm(prompt: str, model: str = "claude-sonnet-4-6"):
    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
```

**Rationale:** LiteLLM enables switching between Claude/GPT without code changes.

---

## Deferred Items

| Item | Deferred To | Reason |
|------|-------------|--------|
| Logic schema versioning | Phase 4 | Need stable schema first |
| Multi-model LLM routing | Phase 4 | Cost optimization later |
| Real-time streaming | Phase 5 | Phase 3 = batch only |
| Backtesting framework | Phase 5 | Need full logic layer first |
| Human review UI | Phase 6 | Web UI phase |
| Logic family sensitivity matrix | Phase 4 | 155 parameters too complex for MVP |

---

## Success Criteria (Phase 3)

1. ✅ LLM identifies logics with required fields (logic_id, direction, family, importance)
2. ✅ Events extracted and associated to logic_ids via two-stage pipeline
3. ✅ Event scorecard applies加减分 rules, decay, validity tracking
4. ✅ Duplicate events detected and filtered via fingerprint validation
5. ✅ Net thrust computed with anti-logic flagging
6. ✅ LLM degradation uses prior day + decay when service unavailable
7. ✅ All data persisted to database with proper indexes
8. ✅ Daily batch job integrated with scheduler

---

## Next Steps

1. **Plan creation:** Generate 6 PLAN.md files for LOGIC-01 through LOGIC-06
2. **Execution:** Run Phase 3 plans (sequential for LLM-dependent tasks)
3. **Verification:** Confirm logic_scores table populated, net_thrust queryable

---

*Context document created: 2026-04-19*
