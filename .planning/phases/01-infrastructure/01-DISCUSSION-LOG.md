# Phase 1: Infrastructure - Discussion Log

**Session**: 2026-04-19  
**Mode**: discuss (default)

---

## Gray Areas Discussed

### 1. Database Strategy

**Question**: MySQL only for simplicity, or dual SQLite (dev) + MySQL (prod)?

**Options**:
1. MySQL only — match production exactly
2. SQLite for local dev, MySQL for production

**User Decision**: MySQL only

**Rationale**: Avoids dual-support complexity, matches production from day 1.

---

### 2. Data Sources Priority

**Question**: All at once (Tushare + 东方财富 + akshare), or start with one?

**Options**:
1. Tushare first — already has Pro token, stable API
2. All sources at once — comprehensive from start

**User Decision**: Tushare first

**Rationale**: Start with stable source, verify data quality, add others incrementally.

---

### 3. Scheduling Architecture

**Question**: Celery + Redis for robustness, or cron + script for simplicity?

**Options**:
1. Celery + Redis — robust, retry logic, monitoring
2. cron + Python script — lightweight, transparent

**User Decision**: cron + script

**Rationale**: Simplest approach, no extra infrastructure, easy to debug via logs.

---

### 4. LLM Logging

**Question**: LiteLLM built-in logging, or custom cost tracking dashboard?

**Options**:
1. LiteLLM built-in + JSON logs — standard approach
2. Custom dashboard — detailed cost analysis

**User Decision**: LiteLLM + JSON logs

**Rationale**: Uses existing LiteLLM integration, no custom dashboard needed in Phase 1.

---

## Decisions Summary

| Decision | Choice | Impact |
|----------|--------|--------|
| D-01 Database | MySQL only | All code targets MySQL 8.0+ directly |
| D-02 Data Sources | Tushare first | Phase 1 implements Tushare only |
| D-03 Scheduling | cron + script | Single script, no Celery/Redis |
| D-04 LLM Logging | LiteLLM + JSON | File-based logs, no dashboard |

---

## Scope Notes

**Deferred** (not Phase 1):
- 东方财富 and akshare integration → Phase 2+
- Custom LLM cost dashboard → Phase 6 (Web UI)
- Celery/Redis infrastructure → Not needed

**Confirmed**:
- Phase 1 goal: Infrastructure foundation only
- Macro scoring → Phase 2
- Event scorecard → Phase 3
- Sector/stock analysis → Phase 4

---

*Discussion complete. CONTEXT.md written with decisions.*
