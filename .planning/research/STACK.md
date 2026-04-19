# Technology Stack

**Project:** A 股智能选股系统 (stock_logic)
**Researched:** 2026-04-19
**Confidence:** HIGH

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | >=0.109.0 | REST API framework | Async-native, automatic OpenAPI docs, Pydantic v2 integration, best Python web framework performance benchmarks |
| Pydantic | >=2.0.0 | Data validation & settings | v2 brings 5-50x performance improvement, Rust core, native FastAPI integration |
| uvicorn[standard] | >=0.27.0 | ASGI server | Official FastAPI recommendation, uvloop + httptools for maximum throughput |
| python-multipart | >=0.0.6 | File/Form handling | Required for FastAPI upload endpoints |

### Database Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLAlchemy | >=2.0.0 | ORM & query builder | Async support via `async_session`, type hints, Alembic migration integration |
| MySQL | 8.0+ | Primary datastore | User-specified, reliable for structured financial data, ACID compliance |
| aiomysql | >=0.2.0 | Async MySQL driver | Native async support for SQLAlchemy 2.0, better than sync driver under load |
| Alembic | >=1.13.0 | Database migrations | SQLAlchemy official migration tool, auto-generation support |

### Data Sources (China A-Share)

| Library | Version | Purpose | Priority |
|---------|---------|---------|----------|
| efinance | >=0.5.5 | 东方财富数据源 | Priority 0 - Highest (free, comprehensive, real-time) |
| akshare | >=1.12.0 | 东方财富爬虫 | Priority 1 - Fallback (broader coverage, slightly slower) |
| tushare | >=1.4.0 | Tushare Pro API | Priority 2 - Premium (requires token, historical data) |
| pytdx | >=1.72 | 通达信行情 | Priority 2 - Real-time quotes |
| baostock | >=0.8.0 | 证券宝 | Priority 3 - Fallback |
| exchange-calendars | >=4.5.0 | 交易日历 | Critical for A-share/HK/US market hours |

### AI/LLM Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| litellm | >=1.80.10,<1.82.7 | Unified LLM client | Single interface for Gemini/Anthropic/OpenAI/DeepSeek, built-in routing & fallback |
| tiktoken | >=0.8.0,<0.12.0 | Token counting | OpenAI's BPE tokenizer, pinned to avoid plugin registration issues |
| openai | >=1.0.0 | OpenAI SDK | Explicit dependency for litellm, async support |
| PyYAML | >=6.0 | LLM config parsing | litellm router configuration |

### Task Scheduling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| APScheduler | >=4.0.0 | Async task scheduler | `schedule` library is sync-only; APScheduler supports async, persistence, cron expressions |
| schedule | >=1.2.0 | Simple cron (legacy) | Keep for compatibility, but migrate to APScheduler |

### Data Processing

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| pandas | >=2.0.0 | Data analysis | Industry standard, Arrow backend for performance |
| numpy | >=1.24.0 | Numerical computation | Vectorized operations for financial calculations |
| openpyxl | >=3.1.0 | Excel import/export | XLSX native support for portfolio imports |
| pypinyin | >=0.50.0 | Chinese-to-pinyin | Stock name matching, fuzzy search |
| json-repair | >=0.55.1 | LLM JSON fix | Handles malformed LLM output gracefully |

### Frontend (React)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 18.x | UI framework | Latest stable, concurrent features |
| TypeScript | 5.x | Type safety | Financial data needs strict typing |
| Vite | 5.x | Build tool | 10-100x faster HMR than webpack, native ES modules |
| TanStack Table | 8.x | Data grid | Headless table logic, sorting/filtering/pagination for stock lists |
| Recharts | 2.x | Financial charts | React-friendly, good enough for radar charts & line graphs |
| Tailwind CSS | 3.x | Styling | Rapid prototyping, consistent design tokens |
| @tanstack/react-query | 5.x | Server state | Caching, background refetch for market data |

### Caching & Performance (Recommended Addition)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| redis-py | >=5.0.0 | Caching layer | Market data caching, LLM response deduplication, rate limiting |
| hiredis | >=2.8.0 | Redis parser | C extension for 2-3x faster serialization |

### Logging & Observability

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| structlog | >=24.0.0 | Structured logging | JSON logs, correlation IDs for request tracing |
| python-json-logger | >=2.0.0 | JSON log formatting | ELK/CloudWatch compatible output |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web Framework | FastAPI | Django REST Framework | DRF is sync-first, slower for high-concurrency market data |
| Database | MySQL + SQLAlchemy | PostgreSQL | User specified MySQL; no strong reason to switch |
| ORM | SQLAlchemy 2.0 | Tortoise ORM | SQLAlchemy has better ecosystem, Alembic integration |
| Async MySQL | aiomysql | asyncmy | asyncmy is fork of aiomysql with marginally better perf, but less maintenance |
| Scheduler | APScheduler | Celery | Celery overkill for daily batch jobs; no distributed task needs |
| Frontend | React + Vite | Next.js | SSR not needed; dashboard is client-side heavy |
| Charts | Recharts | Plotly/Dash | Plotly heavier, overkill for simple radar/line charts |
| State Mgmt | React Query | Redux/Zustand | Redux boilerplate unnecessary; React Query handles server state |
| LLM Client | litellm | Direct SDK calls | litellm provides unified interface, fallback routing, cost tracking |
| Data Source | efinance | akshare only | efinance has better real-time coverage; use both for redundancy |

## Installation

```bash
# Core Backend
pip install fastapi uvicorn[standard] python-multipart
pip install sqlalchemy alembic aiomysql
pip install pydantic pydantic-settings

# Data Sources
pip install efinance akshare tushare pytdx baostock exchange-calendars

# AI/LLM
pip install "litellm>=1.80.10,<1.82.7" "tiktoken>=0.8.0,<0.12.0" openai PyYAML

# Data Processing
pip install pandas numpy openpyxl pypinyin json-repair

# Task Scheduling (replace `schedule` with APScheduler)
pip install apscheduler

# Caching (Recommended)
pip install redis hiredis

# Logging
pip install structlog python-json-logger

# Dev Dependencies
pip install pytest pytest-asyncio httpx ruff mypy

# Frontend
cd frontend
npm create vite@latest . -- --template react-ts
npm install @tanstack/react-table recharts @tanstack/react-query tailwindcss
```

## Stack Rationale

### Why This Stack for Quantitative Trading

1. **Async-first architecture** - Market data feeds, LLM calls, and database queries all benefit from async I/O. FastAPI + uvicorn + aiomysql provides end-to-end async pipeline.

2. **Data source redundancy** - China A-share data sources can be unreliable. Priority-based fallback (efinance → akshare → tushare) ensures resilience.

3. **LLM cost control** - litellm router enables rate limiting, fallback between providers (e.g., DeepSeek as cheaper alternative to Claude), and token tracking.

4. **Type safety end-to-end** - Pydantic v2 + TypeScript ensures data contracts are enforced from database to UI, critical for financial applications.

5. **Maintainability** - SQLAlchemy 2.0 + Alembic for migrations, APScheduler for cron jobs, React Query for server state. All are well-documented, widely adopted patterns.

### Phase 0.5 MVP Scope

For MVP, focus on:
- FastAPI + MySQL + SQLAlchemy (core)
- efinance + akshare (data)
- litellm (LLM abstraction)
- APScheduler (daily batch jobs)
- React + Vite + TanStack Table (dashboard)

**Defer to Phase 1+**: Redis caching, structlog, comprehensive testing setup, advanced charting (TradingView integration).

## Sources

- FastAPI official documentation (fastapi.tiangolo.com) - HIGH confidence
- SQLAlchemy 2.0 documentation (docs.sqlalchemy.org) - HIGH confidence
- Pydantic v2 migration guide (docs.pydantic.dev) - HIGH confidence
- litellm documentation (docs.litellm.ai) - HIGH confidence
- TanStack documentation (tanstack.com) - HIGH confidence
- GitHub: efinance, akshare, tushare repositories - HIGH confidence
- Community benchmarks and best practices (2024-2025) - MEDIUM confidence
