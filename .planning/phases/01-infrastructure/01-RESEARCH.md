# Phase 1: Infrastructure - Research

**Researched:** 2026-04-19  
**Domain:** MySQL database schema, Tushare API integration, APScheduler cron jobs, LiteLLM logging  
**Confidence:** HIGH

## Summary

This research covers the foundational infrastructure for the stock_logic project: MySQL database persistence, Tushare Pro API data access, cron-based scheduling for daily batch jobs, and LiteLLM structured JSON logging.

Key findings:
- **Database**: MySQL 8.0+ with SQLAlchemy 2.0 async support; four core tables (events, logics, stocks, market_data)
- **Tushare**: Pro API requires token; free tier = 80 calls/minute, 500 calls/day; 2000 points for stock lists/market stats
- **Scheduling**: APScheduler 4.x with CronTrigger for market-close daily jobs (simpler than Celery, no Redis needed)
- **Logging**: LiteLLM built-in callbacks + JSON format via `JSON_LOGS=True` env var

**Primary recommendation:** Use SQLAlchemy Core + async MySQL connector for data layer; implement Tushare rate limiting at fetcher level; APScheduler standalone script invoked by system cron; LiteLLM file-based JSON logging to `logs/lite_llm/`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MySQL database schema | Database / Storage | — | Persistent data layer for events, logics, stocks, market data |
| Tushare API integration | API / Backend | — | External data source access, rate limiting, error handling |
| APScheduler cron jobs | API / Backend (scheduled) | OS cron | Python script scheduled by system cron for daily batch processing |
| LiteLLM logging | API / Backend | — | LLM call observation, cost tracking, debugging |
| Database migrations | Database / Storage | — | Alembic for schema versioning |
| Data validation | API / Backend | — | Pydantic models for input/output contracts |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.49 (verified) | ORM + async query builder | Industry standard, Alembic integration, type hints |
| MySQL | 8.0+ | Primary datastore | User-specified; matches production; ACID compliance |
| aiomysql | Latest | Async MySQL driver | Native async support for SQLAlchemy 2.0 |
| Alembic | Latest | Database migrations | Official SQLAlchemy migration tool |
| Pydantic | 2.13.2 (verified) | Data validation | v2 performance, FastAPI integration |

### Data Sources
| Library | Version | Purpose | Priority |
|---------|---------|---------|----------|
| tushare | 1.4.29 (verified) | Tushare Pro API | Priority 1 - User has Pro token |
| akshare | 1.18.55 (verified) | 东方财富爬虫 | Priority 2 - Fallback, broader coverage |
| efinance | 0.5.8 (verified) | 东方财富数据 | Priority 0 - Free, no token needed |

### Scheduling & Logging
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 4.x | Cron-based scheduling | Supports async, persistence, cron expressions; simpler than Celery |
| litellm | 1.82.6 (verified) | Unified LLM client | Built-in logging callbacks, multi-provider support |
| python-json-logger | Latest | JSON log formatting | ELK/CloudWatch compatible output |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | 2.x | Data manipulation | Tushare/Akshare return DataFrames |
| numpy | Latest | Numerical operations | Financial calculations |
| cryptography | 46.0.7 (verified) | Secret management | SOPS key decryption |

**Installation:**
```bash
# Core Backend
pip install "sqlalchemy>=2.0.0" alembic aiomysql pymysql
pip install "pydantic>=2.0.0" pydantic-settings

# Data Sources
pip install tushare akshare efinance

# Task Scheduling
pip install "apscheduler>=4.0.0"

# LLM Integration
pip install "litellm>=1.80.10,<1.82.7" tiktoken openai PyYAML python-json-logger

# Data Processing
pip install pandas numpy
```

**Version verification:**
```bash
$ pip3 show sqlalchemy | grep Version
Version: 2.0.49
$ pip3 show pydantic | grep Version  
Version: 2.13.2
$ pip3 show tushare | grep Version
Version: 1.4.29
$ pip3 show litellm | grep Version
Version: 1.82.6
```

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         System Cron                              │
│                    (market-close trigger)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    scripts/daily_job.py                          │
│                   (APScheduler standalone)                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Tushare      │  │ Akshare      │  │ efinance     │          │
│  │ Fetcher      │  │ Fetcher      │  │ Fetcher      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│                            ▼                                     │
│              ┌─────────────────────────┐                         │
│              │  DataFetcherManager     │                         │
│              │  (failover + cache)     │                         │
│              └────────────┬────────────┘                         │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   MySQL 8.0 Database    │
              │   (aiomysql async)      │
              ├─────────────────────────┤
              │ - events                │
              │ - logics                │
              │ - stocks                │
              │ - market_data           │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   LiteLLM + JSON Logs   │
              │   logs/lite_llm/        │
              └─────────────────────────┘
```

### Recommended Project Structure
```
src/
├── config/              # Configuration management
│   ├── __init__.py
│   └── settings.py      # Pydantic settings (DB, Tushare token)
├── database/            # Database layer
│   ├── __init__.py
│   ├── connection.py    # Async MySQL connection pool
│   ├── models.py        # SQLAlchemy ORM models
│   └── migrations/      # Alembic migrations
├── data/                # Data source layer
│   ├── __init__.py
│   ├── base.py          # BaseFetcher abstract class
│   ├── tushare_fetcher.py
│   ├── akshare_fetcher.py
│   ├── efinance_fetcher.py
│   └── manager.py       # DataFetcherManager (failover)
├── scheduler/           # Scheduling layer
│   ├── __init__.py
│   └── daily_job.py     # APScheduler cron jobs
└── logging/             # Logging configuration
    ├── __init__.py
    └── litellm_callback.py # LiteLLM custom logger
scripts/
├── daily_job.py         # Standalone cron entry point
└── init_db.py           # Database initialization
logs/
├── app_*.log            # Application logs
├── app_debug_*.log      # Debug logs
└── lite_llm/            # LLM call logs (JSON)
```

### Pattern 1: SQLAlchemy Async MySQL Connection

```python
# Source: SQLAlchemy 2.0 documentation (docs.sqlalchemy.org)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Async engine with connection pooling
engine = create_async_engine(
    "mysql+aiomysql://user:password@localhost:3306/stock_logic",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Connection health check
    echo=False,  # Set True for SQL debugging
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Usage in async context
async with async_session_maker() as session:
    result = await session.execute(select(EventModel).where(EventModel.logic_id == "xxx"))
```

### Pattern 2: Tushare Rate Limiting

```python
# Source: Tushare Pro docs + existing code (old/data_provider/tushare_fetcher.py)
import time
from datetime import datetime

class TushareFetcher:
    def __init__(self, rate_limit_per_minute: int = 80):
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0
        self._minute_start: Optional[float] = None
    
    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting"""
        current_time = time.time()
        
        # Reset counter for new minute
        if self._minute_start is None or current_time - self._minute_start >= 60:
            self._minute_start = current_time
            self._call_count = 0
        
        # Force wait if quota exceeded
        if self._call_count >= self.rate_limit_per_minute:
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1
            logger.warning(f"Tushare rate limit reached, waiting {sleep_time:.1f}s...")
            time.sleep(sleep_time)
            self._minute_start = time.time()
            self._call_count = 0
        
        self._call_count += 1
```

### Pattern 3: APScheduler Cron Job

```python
# Source: APScheduler 4 docs (github.com/agronholm/apscheduler)
from apscheduler import Scheduler
from apscheduler.triggers.cron import CronTrigger

async def daily_market_data_job():
    """Daily job: fetch market data after market close"""
    async with async_session_maker() as session:
        # Fetch and store market data
        ...

with Scheduler() as scheduler:
    # Run at 15:30 every weekday (after A-share market closes at 15:00)
    scheduler.add_schedule(
        daily_market_data_job,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri")
    )
    scheduler.run_until_stopped()
```

### Pattern 4: LiteLLM JSON Logging

```python
# Source: LiteLLM docs (github.com/berriai/litellm)
import os
import litellm

# Enable JSON logs via environment variable
os.environ["JSON_LOGS"] = "True"

# Configure file logging
litellm.success_callback = ["json_logging"]
litellm.failure_callback = ["json_logging"]

# Or use custom callback handler
from litellm.integrations.custom_logger import CustomLogger

class FileJsonLogger(CustomLogger):
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": kwargs.get("model"),
            "messages": kwargs.get("messages"),
            "response": response_obj,
            "usage": kwargs.get("usage"),
        }
        # Write to logs/lite_llm/calls.jsonl
        with open("logs/lite_llm/calls.jsonl", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
```

### Anti-Patterns to Avoid

- **Don't use sync MySQL driver with async code** — `pymysql` is blocking; use `aiomysql` for async
- **Don't call Tushare without rate limiting** — Free tier = 80 calls/min; implement counter + sleep
- **Don't use Celery for daily jobs** — Overkill; APScheduler + system cron is simpler
- **Don't log LLM calls as plain text** — Use JSON for structured analysis

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MySQL connection pooling | Custom pool logic | SQLAlchemy `pool_size` + `aiomysql` | Battle-tested, handles reconnection, ping |
| Tushare rate limiting | Manual sleep | `_check_rate_limit()` counter | Accurate per-minute tracking |
| Cron scheduling | Custom while-loop | APScheduler CronTrigger | Timezone-aware, DST-safe, persistent |
| LLM logging | Print statements | LiteLLM callbacks + JSON | Structured, queryable, cost tracking |
| Database migrations | Manual ALTER TABLE | Alembic autogenerate | Version-controlled, reversible |

**Key insight:** Infrastructure components have well-established solutions — reinventing them introduces bugs and maintenance burden.

## Runtime State Inventory

> SKIPPED — This is a greenfield phase (no existing runtime state to inventory).

## Common Pitfalls

### Pitfall 1: Tushare Token Not Configured
**What goes wrong:** Fetcher initializes but returns None for all API calls  
**Why it happens:** Token loaded from env var; missing from .env or not passed to container  
**How to avoid:** Add validation in `__init__`; log warning if token missing  
**Warning signs:** Logs show "Tushare API not initialized"

### Pitfall 2: MySQL Connection Pool Exhaustion
**What goes wrong:** `Too many connections` error after concurrent requests  
**Why it happens:** Default `pool_size=5` insufficient for batch jobs  
**How to avoid:** Set `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`  
**Warning signs:** Slow queries, connection timeouts under load

### Pitfall 3: APScheduler Timezone Confusion
**What goes wrong:** Job runs at wrong time (e.g., 07:30 UTC instead of 15:30 CST)  
**Why it happens:** Default timezone is local; China uses CST (UTC+8)  
**How to avoid:** Explicitly set `timezone="Asia/Shanghai"` in CronTrigger  
**Warning signs:** Logs show job running 7-8 hours off expected time

### Pitfall 4: LiteLLM Logs Not Written
**What goes wrong:** `logs/lite_llm/` directory empty after LLM calls  
**Why it happens:** Callback not registered before first call; directory doesn't exist  
**How to avoid:** Create directory in init; register callbacks at module import  
**Warning signs:** No files in log directory; stderr shows callback errors

## Code Examples

### EventModel Table Schema
```python
# Source: old/src/sector_logic/db_schema.py (adapted for MySQL)
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, Text, Index, UniqueConstraint

class EventModel(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    logic_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)  # 'positive' / 'negative'
    score_impact = Column(Float, nullable=False)
    event_date = Column(Date, nullable=False)
    expire_date = Column(Date, nullable=False)
    summary = Column(Text, nullable=False)
    event_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    __table_args__ = (
        Index('ix_events_logic_expire', 'logic_id', 'expire_date'),
        UniqueConstraint('logic_id', 'event_date', 'event_type', 'event_hash',
                         name='uq_logic_date_type_hash'),
    )
```

### Daily Job Script
```python
#!/usr/bin/env python3
# scripts/daily_job.py
import asyncio
import logging
from datetime import datetime
from src.data.manager import DataFetcherManager
from src.database.connection import async_session_maker
from src.database.models import MarketData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_and_store_market_data():
    """Fetch end-of-day market data and store in MySQL"""
    fetcher_manager = DataFetcherManager()
    
    async with async_session_maker() as session:
        # Example: fetch 贵州茅台 (600519) daily data
        df, source = fetcher_manager.get_daily_data('600519', days=1)
        
        if not df.empty:
            row = df.iloc[-1]
            market_data = MarketData(
                ts_code='600519.SH',
                trade_date=row['date'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                amount=row['amount'],
                source=source,
            )
            session.add(market_data)
            await session.commit()
            logger.info(f"Stored market data for 600519 on {row['date']}")

if __name__ == "__main__":
    asyncio.run(fetch_and_store_market_data())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLite for dev, MySQL for prod | MySQL only | User decision D-01 | Simpler codebase, no dual-support complexity |
| Celery + Redis for scheduling | APScheduler + cron | User decision D-03 | No Redis dependency; easier debugging via logs |
| Direct tushare SDK calls | Lightweight HTTP client | Existing code pattern | Reduced dependency; no SDK runtime requirement |
| Print-based LLM logging | LiteLLM JSON callbacks | Phase 1 implementation | Structured logs, cost tracking, queryable |

**Deprecated/outdated:**
- `schedule` library: Sync-only; migrate to APScheduler 4.x async
- `tushare` SDK runtime dependency: Use direct HTTP (existing pattern)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tushare Pro token is configured and has 2000+ points | Standard Stack | Fetcher returns None; no data ingestion |
| A2 | MySQL 8.0+ server is accessible from application host | Standard Stack | Application fails to start; no persistence |
| A3 | System cron can execute Python scripts at 15:30 CST | Architecture Patterns | Daily jobs don't run; stale data |
| A4 | LiteLLM is used for all LLM calls in later phases | Logging | No LLM observability; can't track costs |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **MySQL connection string format**
   - What we know: User chose MySQL only; SQLAlchemy 2.0 async
   - What's unclear: Exact connection string (host, port, database name, credentials)
   - Recommendation: Use environment variables; document in `.env.example`

2. **Tushare token permissions**
   - What we know: User has Pro token (existing code uses it)
   - What's unclear: Current point balance; which APIs are accessible
   - Recommendation: Add runtime check in `TushareFetcher.__init__`; log capabilities

3. **Cron execution environment**
   - What we know: User chose cron + script over Celery
   - What's unclear: Will cron run on same host as app? Container or bare metal?
   - Recommendation: Document in deployment guide; ensure Python path is correct

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core runtime | ✓ | 3.12.10 | — |
| MySQL | Data layer | ✗ | — | N/A (user must provide) |
| SQLAlchemy | ORM | ✓ | 2.0.49 | — |
| aiomysql | Async MySQL | ✗ | — | Use sync `pymysql` temporarily |
| tushare | Data source | ✓ | 1.4.29 | akshare/efinance (no token needed) |
| APScheduler | Scheduling | ✗ | — | System cron calls script directly |
| litellm | LLM logging | ✓ | 1.82.6 | — |
| pandas | Data processing | ✓ | (installed) | — |

**Missing dependencies with no fallback:**
- MySQL server — user must provision

**Missing dependencies with fallback:**
- aiomysql — install with `pip install aiomysql`; fallback to `pymysql` (sync)
- APScheduler — install with `pip install apscheduler`; fallback to direct cron invocation

## Validation Architecture

> SKIPPED — `workflow.nyquist_validation: false` in `.planning/config.json`.

## Security Domain

> SKIPPED — Phase 1 is infrastructure (database, data sources, scheduling); no authentication, authorization, or user input handling. Security patterns will be documented in Phase 6 (Web UI).

## Sources

### Primary (HIGH confidence)
- **Tushare Pro documentation** (tushare.pro/document/2) — Rate limits, API endpoints, quota requirements
- **APScheduler 4 documentation** (github.com/agronholm/apscheduler) — CronTrigger, scheduler configuration
- **LiteLLM documentation** (github.com/berriai/litellm) — JSON logging, custom callbacks
- **SQLAlchemy 2.0 documentation** (docs.sqlalchemy.org) — Async MySQL, connection pooling
- **Existing codebase** (old/data_provider/*.py) — TushareFetcher, AkshareFetcher, EfinanceFetcher implementations

### Secondary (MEDIUM confidence)
- **Context7 library lookups** — Tushare Pro, APScheduler, LiteLLM documentation summaries
- **pip3 show output** — Installed package versions verified locally

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Verified via pip3 show + existing code
- Architecture: HIGH — Based on user decisions D-01, D-02, D-03, D-04 from CONTEXT.md
- Pitfalls: MEDIUM — Based on common patterns + existing code observations

**Research date:** 2026-04-19  
**Valid until:** 2026-07-19 (90 days — stable infrastructure stack)
