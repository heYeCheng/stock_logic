---
phase: 01-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/database/connection.py
  - src/database/models.py
  - src/database/__init__.py
  - pyproject.toml
autonomous: true
requirements:
  - INFRA-01

must_haves:
  truths:
    - "Database connection can be established to MySQL 8.0+"
    - "Four core tables (events, logics, stocks, market_data) are created"
    - "Alembic migrations are version-controlled and reversible"
  artifacts:
    - path: "src/database/connection.py"
      provides: "Async MySQL connection pool via SQLAlchemy 2.0 + aiomysql"
      exports: ["async_session_maker", "engine"]
    - path: "src/database/models.py"
      provides: "ORM models for events, logics, stocks, market_data"
      contains: "class EventModel, class LogicModel, class StockModel, class MarketDataModel"
    - path: "alembic/versions/*.py"
      provides: "Initial migration script"
      min_lines: 50
  key_links:
    - from: "src/database/connection.py"
      to: "MySQL 8.0 database"
      via: "mysql+aiomysql connection string"
      pattern: "mysql\\+aiomysql://"
    - from: "src/database/models.py"
      to: "src/database/connection.py"
      via: "Base class import"
      pattern: "from .*connection import Base"
---

<objective>
Set up MySQL database layer with SQLAlchemy 2.0 async support and Alembic migrations for the four core tables.

Purpose: Provide persistent storage for events, logics, stocks, and market data per D-01 (MySQL only, no SQLite dual-support).
Output: Working async MySQL connection pool, ORM models, and initial migration script.
</objective>

<execution_context>
@/Users/heyecheng/.claude/get-shit-done/workflows/execute-plan.md
@/Users/heyecheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-infrastructure/01-CONTEXT.md
@.planning/phases/01-infrastructure/01-RESEARCH.md
@.planning/REQUIREMENTS.md
</context>

<interfaces>
<!-- Key types and contracts from existing codebase -->

From old/src/sector_logic/db_schema.py (legacy SQLite schema - adapt for MySQL):
```python
class EventModel(Base):
    __tablename__ = 'events'
    # Columns: id, logic_id, event_type, direction, score_impact, event_date, expire_date, summary, event_hash, created_at

class LogicModel(Base):
    __tablename__ = 'logics'
    # Columns: id, logic_id, logic_name, logic_family, direction, importance_level, is_active, created_at

class StockModel(Base):
    __tablename__ = 'stocks'
    # Columns: id, ts_code, name, industry, concept_sectors, listed_date

class MarketDataModel(Base):
    __tablename__ = 'market_data'
    # Columns: id, ts_code, trade_date, open, high, low, close, volume, amount, source
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Install dependencies and create database module skeleton</name>
  <files>pyproject.toml, src/database/__init__.py</files>
  <action>
    Add dependencies to pyproject.toml:
    - sqlalchemy>=2.0.0
    - aiomysql
    - pymysql (sync fallback)
    - alembic
    
    Create src/database/__init__.py with exports for connection and models.
    
    Run: pip install -e ".[database]" to install new dependencies.
  </action>
  <verify>
    <automated>pip show sqlalchemy aiomysql alembic | grep -E "^Version:"</automated>
  </verify>
  <done>
    Dependencies installed and verified via pip show; src/database/__init__.py exports connection and models.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create async MySQL connection pool</name>
  <files>src/database/connection.py</files>
  <action>
    Create src/database/connection.py with:
    1. Async engine using mysql+aiomysql:// connection string from DATABASE_URL env var
    2. Connection pool: pool_size=10, max_overflow=20, pool_pre_ping=True
    3. AsyncSession factory (async_session_maker)
    4. Base = declarative_base() for ORM models
    5. get_async_session() dependency injector for FastAPI (future use)
    
    Connection string format: mysql+aiomysql://{user}:{password}@{host}:{port}/{database}
    
    Per D-01: No SQLite fallback code. MySQL only.
  </action>
  <verify>
    <automated>python -c "from src.database.connection import engine, async_session_maker, Base; print('OK')"</automated>
  </verify>
  <done>
    Module imports without error; engine configured with aiomysql and pool settings; async_session_maker is callable.
  </done>
</task>

<task type="auto">
  <name>Task 3: Define ORM models for events, logics, stocks, market_data</name>
  <files>src/database/models.py</files>
  <action>
    Create src/database/models.py with four ORM models adapted from legacy schema:
    
    1. EventModel (table: events):
       - id (PK, autoincrement), logic_id (indexed), event_type, direction, score_impact (Float)
       - event_date (Date), expire_date (Date), summary (Text), event_hash (String 64)
       - created_at (DateTime, default=now)
       - Index: ix_events_logic_expire (logic_id, expire_date)
       - UniqueConstraint: (logic_id, event_date, event_type, event_hash)
    
    2. LogicModel (table: logics):
       - id (PK), logic_id (unique, indexed), logic_name, logic_family, direction
       - importance_level (String: low/medium/high), is_active (Boolean, default=True)
       - created_at (DateTime, default=now)
       - Index: ix_logics_family (logic_family)
    
    3. StockModel (table: stocks):
       - id (PK), ts_code (unique, indexed), name, industry, concept_sectors (Text)
       - listed_date (Date), created_at (DateTime, default=now)
       - Index: ix_stocks_code (ts_code)
    
    4. MarketDataModel (table: market_data):
       - id (PK), ts_code (indexed), trade_date (Date, indexed)
       - open, high, low, close (Float), volume (BigInteger), amount (Float)
       - source (String: tushare/akshare/efinance), created_at (DateTime, default=now)
       - Index: ix_market_data_code_date (ts_code, trade_date)
    
    All models inherit from Base (imported from connection.py).
    Use sqlalchemy.sql.func.now() for default timestamps.
  </action>
  <verify>
    <automated>python -c "from src.database.models import EventModel, LogicModel, StockModel, MarketDataModel; print('OK')"</automated>
  </verify>
  <done>
    All four models import without error; each has __tablename__, primary key, and required columns defined.
  </done>
</task>

<task type="auto">
  <name>Task 4: Initialize Alembic and create initial migration</name>
  <files>alembic.ini, alembic/env.py, alembic/versions/001_initial_schema.py</files>
  <action>
    1. Run: alembic init alembic (if alembic/ doesn't exist)
    2. Configure alembic.ini:
       - sqlalchemy.url = mysql+aiomysql://user:pass@localhost:3306/stock_logic (use env var)
       - file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(rev)s_%%(slug)s
    3. Edit alembic/env.py:
       - Import target_metadata = src.database.models.Base.metadata
       - Configure async MySQL support for migrations
    4. Run: alembic revision --autogenerate -m "Initial schema: events, logics, stocks, market_data"
    5. Verify migration script contains all four tables.
  </action>
  <verify>
    <automated>alembic current</automated>
  </verify>
  <done>
    Alembic configured; initial migration script created in alembic/versions/; alembic current shows head revision.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Application → MySQL | Database credentials must be protected; connection string from env vars |
| Environment → Application | DATABASE_URL and secrets loaded from environment, not hardcoded |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | DATABASE_URL env var | mitigate | Load from .env file (not committed); document in .env.example; never log connection string |
| T-01-02 | Tampering | Database migrations | mitigate | Use Alembic version control; review migration scripts before applying; no manual ALTER TABLE |
| T-01-03 | Spoofing | MySQL authentication | mitigate | Use dedicated database user with least-privilege (no DROP/DELETE on production) |
| T-01-04 | Repudiation | Schema changes | accept | Migration scripts are version-controlled in git; audit trail via commit history |
</threat_model>

<verification>
- Database connection test: python -c "from src.database.connection import async_session_maker; print('OK')"
- Models import test: python -c "from src.database.models import EventModel, LogicModel, StockModel, MarketDataModel; print('OK')"
- Alembic migration test: alembic upgrade head (on test database)
</verification>

<success_criteria>
1. SQLAlchemy 2.0 + aiomysql installed and verified
2. Async connection pool configured with pool_size=10, max_overflow=20, pool_pre_ping=True
3. Four ORM models defined with correct columns, indexes, and constraints
4. Alembic migration script generated and contains all four tables
5. No SQLite-related code present (per D-01)
</success_criteria>

<output>
After completion, create .planning/phases/01-infrastructure/01-01-SUMMARY.md
</output>
