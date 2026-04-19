# Roadmap: 交易逻辑驱动的智能选股系统 (stock_logic)

**Version**: Phase 0.5 MVP  
**Created**: 2026-04-19  
**Granularity**: coarse  
**Total Phases**: 6

---

## Phases

- [x] **Phase 1: Infrastructure** - Database, data sources, scheduling foundation
- [x] **Phase 2: Macro Environment** - L0 macro scoring and regime detection
- [x] **Phase 3: Logic Layer** - L1 event scorecard and LLM logic extraction - 12/12 tests pass
- [x] **Phase 4: Market Layer** - L2 sector market radar and L3 stock scoring - 13/13 plans complete
- [x] **Phase 5: Execution** - L4 position function and trading constraints
- [ ] **Phase 6: Web UI** - FastAPI REST API + React dashboard

---

## Phase Details

### Phase 1: Infrastructure

**Goal**: Foundational data persistence, external data access, and automated scheduling

**Depends on**: Nothing (first phase)

**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04

**Success Criteria** (what must be TRUE):
  1. Database tables exist and can store events, logics, stocks, and market data
  2. Daily scheduled jobs run automatically after market close
  3. System can fetch data from Tushare, 东方财富，and akshare without manual intervention
  4. LLM calls and data source health are logged for monitoring

**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — MySQL database layer with SQLAlchemy 2.0 async, ORM models, Alembic migrations
- [ ] 01-02-PLAN.md — Tushare primary fetcher with rate limiting, Akshare/Efinance fallbacks
- [ ] 01-03-PLAN.md — APScheduler + cron daily job for post-market data ingestion
- [ ] 01-04-PLAN.md — LiteLLM JSON logging and application health monitoring

---

### Phase 2: Macro Environment

**Goal**: Macro environment scoring and regime detection to set overall market exposure

**Depends on**: Phase 1 (data infrastructure)

**Requirements**: MACRO-01, MACRO-02, MACRO-03, MACRO-04

**Success Criteria** (what must be TRUE):
  1. System outputs five-dimension macro scores (liquidity, growth, inflation cost, policy, global)
  2. Monetary-credit quadrant is determined with macro_multiplier calculated
  3. Macro data updates monthly with event-triggered refresh capability
  4. System gracefully degrades to macro_multiplier = 1.00 when data unavailable

**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Macro five-dimension scoring module (liquidity, growth, inflation, policy, global)
- [x] 02-02-PLAN.md — Monetary-credit quadrant determination + macro_multiplier calculation
- [x] 02-03-PLAN.md — Monthly refresh scheduler (15th 16:00 CST) with event-triggered stub
- [x] 02-04-PLAN.md — Graceful degradation strategy (partial/limited/minimal data fallback)

---

### Phase 3: Logic Layer

**Goal**: LLM-driven logic identification and event scorecard rule engine

**Depends on**: Phase 1 (infrastructure), Phase 2 (macro context)

**Requirements**: LOGIC-01, LOGIC-02, LOGIC-03, LOGIC-04, LOGIC-05, LOGIC-06

**Success Criteria** (what must be TRUE):
  1. LLM identifies and categorizes logics with logic_id, direction, logic_family, importance_level
  2. Events are extracted and associated to logic_ids in two-stage pipeline
  3. Event scorecard applies加减分 rules, natural decay, and tracks validity periods
  4. Duplicate events are detected and filtered via fingerprint validation
  5. Net thrust is calculated with anti-logic flagging
  6. LLM service degradation uses previous day's data with decay applied

**Plans**: 6 plans

Plans:
- [x] 03-01-PLAN.md — LLM logic identification service (logic_id, direction, family, importance)
- [x] 03-02-PLAN.md — LLM event extraction service (two-stage pipeline)
- [x] 03-03-PLAN.md — Event scorecard rule engine (加减分，decay, validity)
- [x] 03-04-PLAN.md — Event fingerprint validation (deduplication)
- [x] 03-05-PLAN.md — Net thrust calculation (anti-logic flagging)
- [x] 03-06-PLAN.md — LLM service degradation strategy (fallback)

---

### Phase 4: Market Layer

**Goal**: Pure volume-price market analysis for sectors and individual stocks

**Depends on**: Phase 1 (data), Phase 3 (logic scores)

**Requirements**: MARKET-01, MARKET-02, MARKET-03, MARKET-04, MARKET-05, STOCK-01, STOCK-02, STOCK-03, STOCK-04, STOCK-05, STOCK-06, STOCK-07, STOCK-08

**Success Criteria** (what must be TRUE):
  1. Sector market radar outputs technical + sentiment scores
  2. Sector three-state 判定 (weak/normal/overheated) is computed
  3. Lead concentration is calculated (替代分支分析)
  4. Structure markers output (聚焦/扩散/快速轮动)
  5. Tushare limit board data (limit_list, top_inst) is ingested
  6. Stock-sector mapping table exists with industry + concept affiliations
  7. Exposure coefficient computed (affiliation_strength × logic_match_score)
  8. LLM generates 5-8 keywords for new sectors automatically
  9. Individual stock logic score (stock_logic_score) is calculated
  10. Individual stock market radar outputs technical + sentiment scores
  11. Catalyst markers simplified to strong/medium/none
  12. Dragon leader/zhongjun/follower identification is performed
  13. Individual stock composite score computed (50% logic + 50% market)

**Plans**: 13 plans

Plans:
- [x] MARKET-01-PLAN.md — Sector market radar (technical + sentiment scores)
- [x] MARKET-02-PLAN.md — Sector three-state determination (weak/normal/overheated)
- [x] MARKET-03-PLAN.md — Lead concentration calculation (HHI-based)
- [x] MARKET-04-PLAN.md — Structure markers (聚焦/扩散/快速轮动)
- [x] MARKET-05-PLAN.md — Tushare limit board data ingestion
- [x] STOCK-01-PLAN.md — Stock-sector mapping table
- [x] STOCK-02-PLAN.md — Exposure coefficient calculation
- [x] STOCK-03-PLAN.md — Keyword auto-generation (LLM)
- [x] STOCK-04-PLAN.md — Stock logic score
- [x] STOCK-05-PLAN.md — Stock market radar
- [x] STOCK-06-PLAN.md — Catalyst markers (strong/medium/none)
- [x] STOCK-07-PLAN.md — Dragon/zhongjun/follower identification
- [x] STOCK-08-PLAN.md — Composite score (50% logic + 50% market)

**UI hint**: yes

---

### Phase 5: Execution

**Goal**: Continuous position function and A-share trading constraint enforcement

**Depends on**: Phase 3 (logic scores), Phase 4 (stock scores)

**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04

**Success Criteria** (what must be TRUE):
  1. Continuous position function outputs position recommendations (replacing discrete matrix)
  2. A-share trading constraints are enforced (limit up/down, suspension, chasing risk)
  3. Stock recommendation markers applied (逻辑受益股/关联受益股/情绪跟风股)
  4. Stop-loss and hold decision rules are applied consistently

**Plans**: 4 plans

Plans:
- [x] EXEC-01-PLAN.md — Continuous position function with macro and sector overlays
- [x] EXEC-02-PLAN.md — A-share trading constraints (limit up/down, suspension, chasing risk)
- [x] EXEC-03-PLAN.md — Stock recommendation markers (逻辑受益股/关联受益股/情绪跟风股)
- [x] EXEC-04-PLAN.md — Stop-loss and hold decision rules

---

### Phase 6: Web UI

**Goal**: User-facing dashboard for recommendations, stock details, and configuration

**Depends on**: Phase 2 (macro), Phase 3 (logic), Phase 4 (market/stock), Phase 5 (execution)

**Requirements**: WEB-01, WEB-02, WEB-03, WEB-04

**Success Criteria** (what must be TRUE):
  1. FastAPI REST API serves recommendation list, stock details, and macro overview
  2. React frontend displays stock cards, radar charts, and logic summaries
  3. Users can manually override strength, affiliation strength, and other markers
  4. YAML anchor configuration is editable via web interface with version control

**Plans**: 4 plans

Plans:
- [x] 06-01-PLAN.md — FastAPI REST API (recommendations, stock details, macro overview)
- [ ] 06-02-PLAN.md — React frontend (stock cards, radar charts, logic summaries)
- [ ] 06-03-PLAN.md — Manual override interface (strength, affiliation strength)
- [x] 06-04-PLAN.md — YAML config editor with version control (Dulwich git, diff, revert)

**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 4/4 | ✅ Complete | 2026-04-19 |
| 2. Macro Environment | 4/4 | ✅ Complete | 2026-04-19 |
| 3. Logic Layer | 6/6 | ✅ Complete | 2026-04-19 |
| 4. Market Layer | 13/13 | ✅ Complete | 2026-04-19 |
| 5. Execution | 4/4 | ✅ Complete | 2026-04-19 |
| 6. Web UI | 2/4 | In progress | - |

---

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| MACRO-01 | Phase 2 | ✅ Complete |
| MACRO-02 | Phase 2 | ✅ Complete |
| MACRO-03 | Phase 2 | ✅ Complete |
| MACRO-04 | Phase 2 | ✅ Complete |
| LOGIC-01 | Phase 3 | ✅ Complete |
| LOGIC-02 | Phase 3 | ✅ Complete |
| LOGIC-03 | Phase 3 | ✅ Complete |
| LOGIC-04 | Phase 3 | ✅ Complete |
| LOGIC-05 | Phase 3 | ✅ Complete |
| LOGIC-06 | Phase 3 | ✅ Complete |
| MARKET-01 | Phase 4 | Pending |
| MARKET-02 | Phase 4 | Pending |
| MARKET-03 | Phase 4 | Pending |
| MARKET-04 | Phase 4 | Pending |
| MARKET-05 | Phase 4 | Pending |
| STOCK-01 | Phase 4 | Pending |
| STOCK-02 | Phase 4 | Pending |
| STOCK-03 | Phase 4 | Pending |
| STOCK-04 | Phase 4 | Pending |
| STOCK-05 | Phase 4 | Pending |
| STOCK-06 | Phase 4 | Pending |
| STOCK-07 | Phase 4 | Pending |
| STOCK-08 | Phase 4 | Pending |
| EXEC-01 | Phase 5 | ✅ Complete |
| EXEC-02 | Phase 5 | ✅ Complete |
| EXEC-03 | Phase 5 | ✅ Complete |
| EXEC-04 | Phase 5 | ✅ Complete |
| WEB-01 | Phase 6 | Pending |
| WEB-02 | Phase 6 | Pending |
| WEB-03 | Phase 6 | Pending |
| WEB-04 | Phase 6 | Pending |

**Coverage Summary**:
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

---

*Last updated: 2026-04-19*
