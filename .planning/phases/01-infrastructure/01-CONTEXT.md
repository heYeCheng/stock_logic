# Phase 1: Infrastructure - Context

**Gathered**: 2026-04-19  
**Status**: Ready for planning

<domain>
## Phase Boundary

Foundational data persistence, external data access, and automated scheduling

**In scope**:
- Database tables for events, logics, stocks, market data
- Daily scheduled jobs post-market close
- Data source integration (Tushare, 东方财富，akshare)
- LLM and data source health logging

**Out of scope**:
- Macro scoring logic (Phase 2)
- Event scorecard rules (Phase 3)
- Sector/stock market analysis (Phase 4)
- Web UI (Phase 6)
</domain>

<decisions>
## Implementation Decisions

### Database Strategy

**D-01**: MySQL only — match production exactly, no SQLite dual-support

| Considered | Chosen | Why |
|------------|--------|-----|
| SQLite for dev, MySQL for prod | MySQL only | User explicitly stated "MySQL only" — avoids dual-support complexity, matches production from day 1 |

**How to apply**: All database code targets MySQL 8.0+ directly. No ORM abstraction for database switching.

---

### Data Sources Priority

**D-02**: Tushare first approach — start with stable Tushare API (has token), add 东方财富 and akshare incrementally

| Considered | Chosen | Why |
|------------|--------|-----|
| Integrate all sources at once | Tushare first | User confirmed "Tushare first" — already has Pro token, stable API, can verify data quality before adding complexity |

**How to apply**: Phase 1 implements Tushare integration only. 东方财富 and akshare added in Phase 2+ as fallback sources.

---

### Scheduling Architecture

**D-03**: cron + Python script — lightweight and transparent, no Celery/Redis overhead

| Considered | Chosen | Why |
|------------|--------|-----|
| Celery + Redis | cron + script | User chose "cron + script" — simplest approach, no extra infrastructure, easy to debug via logs |

**How to apply**: Single Python script (`scripts/daily_job.py`) invoked by system cron. No Celery workers, no Redis broker.

---

### LLM Logging

**D-04**: LiteLLM built-in logging + structured JSON logs — standard approach without custom cost tracking

| Considered | Chosen | Why |
|------------|--------|-----|
| Custom cost tracking dashboard | LiteLLM + JSON logs | User chose "LiteLLM + JSON logs" — uses existing LiteLLM integration, logs to JSON files for monitoring |

**How to apply**: Configure LiteLLM callback to write JSON logs to `logs/lite_llm/`. No custom dashboard in Phase 1.
</decisions>

<constraints>
## Technical Constraints

- **Python**: 3.10+ (for asyncio, typing)
- **Database**: MySQL 8.0+ (InnoDB engine)
- **Scheduling**: System cron (Unix/Linux/macOS)
- **Logging**: JSON format, file-based (no ELK stack in Phase 1)
</constraints>

<risks>
## Known Risks

| Risk | Mitigation |
|------|------------|
| Tushare API rate limits | Implement request throttling, cache responses |
| Cron job failures | Log to file, user monitors manually |
| MySQL connection pool exhaustion | Use connection pooling (SQLAlchemy), configure pool_size |
| LLM service degradation | Phase 3 implements fallback to previous day + decay |
</risks>

---
*Next step: `/gsd-plan-phase 1` to create detailed implementation plan*
