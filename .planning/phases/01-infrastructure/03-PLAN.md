---
phase: 01-infrastructure
plan: 03
type: execute
wave: 2
depends_on:
  - 01-infrastructure-01
  - 01-infrastructure-02
files_modified:
  - scripts/daily_job.py
  - src/scheduler/__init__.py
  - src/scheduler/daily_job.py
  - .env.example
autonomous: false
requirements:
  - INFRA-02

must_haves:
  truths:
    - "APScheduler CronTrigger schedules job at 15:30 CST weekdays"
    - "Daily job fetches stock list and market data after market close"
    - "Job logs execution status to file"
    - "System cron can invoke the script at scheduled time"
  artifacts:
    - path: "scripts/daily_job.py"
      provides: "Standalone cron entry point invoked by system cron"
      exports: ["main"]
    - path: "src/scheduler/daily_job.py"
      provides: "APScheduler scheduler with CronTrigger"
      exports: ["create_scheduler", "daily_market_data_job"]
    - path: ".env.example"
      provides: "Updated with SCHEDULER_TIMEZONE env var"
      contains: "SCHEDULER_TIMEZONE=Asia/Shanghai"
  key_links:
    - from: "scripts/daily_job.py"
      to: "src/scheduler/daily_job.py"
      via: "Import and execution"
      pattern: "from src.scheduler.daily_job import"
    - from: "src/scheduler/daily_job.py"
      to: "src/data/manager.py"
      via: "DataFetcherManager instantiation"
      pattern: "DataFetcherManager\\(\\)"
    - from: "src/scheduler/daily_job.py"
      to: "src/database/connection.py"
      via: "async_session_maker context"
      pattern: "async with async_session_maker"
---

<objective>
Implement daily scheduled job using APScheduler + system cron (D-03) to fetch and store market data after market close.

Purpose: Automate daily data ingestion without manual intervention per INFRA-02.
Output: Standalone Python script scheduled at 15:30 CST weekdays via cron + APScheduler.
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
<!-- Key types from Plan 01 and Plan 02 -->

From src/database/connection.py (Plan 01):
```python
async_session_maker: Callable[[], AsyncSession]
```

From src/database/models.py (Plan 01):
```python
class MarketDataModel(Base):
    # Columns: id, ts_code, trade_date, open, high, low, close, volume, amount, source, created_at
```

From src/data/manager.py (Plan 02):
```python
class DataFetcherManager:
    def get_stock_list() -> pd.DataFrame
    def get_daily_data(ts_code: str, days: int = 1) -> Tuple[pd.DataFrame, str]
```

From src/config/settings.py (Plan 02):
```python
class Settings(BaseSettings):
    tushare_rate_limit: int = 80
    scheduler_timezone: str = "Asia/Shanghai"
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create scheduler module with APScheduler CronTrigger</name>
  <files>src/scheduler/__init__.py, src/scheduler/daily_job.py</files>
  <action>
    Create src/scheduler/__init__.py (empty init).
    
    Create src/scheduler/daily_job.py with:
    
    1. daily_market_data_job() async function:
       - Log job start with timestamp
       - Instantiate DataFetcherManager
       - Fetch stock list via manager.get_stock_list()
       - For each stock (limit 10 for Phase 1 testing):
         - Fetch daily data via manager.get_daily_data(ts_code, days=1)
         - If data present: Create MarketDataModel instance
         - Add to session via async_session_maker
       - Commit all records
       - Log job completion with record count
    
    2. create_scheduler() function:
       - Create Scheduler() instance
       - Add schedule: daily_market_data_job with CronTrigger
       - Cron expression: hour=15, minute=30, day_of_week="mon-fri"
       - Timezone: Asia/Shanghai (per RESEARCH.md Pitfall 3)
       - Return scheduler
    
    3. run_scheduler() function:
       - Create scheduler via create_scheduler()
       - Call scheduler.run_until_stopped()
       - Handle KeyboardInterrupt gracefully
  </action>
  <verify>
    <automated>python -c "from src.scheduler.daily_job import create_scheduler; s = create_scheduler(); print(f'Schedules: {len(s.get_jobs())}')"</automated>
  </verify>
  <done>
    Scheduler created with one job; CronTrigger configured for 15:30 mon-fri Asia/Shanghai; job function is async.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create standalone cron entry point script</name>
  <files>scripts/daily_job.py</files>
  <action>
    Create scripts/daily_job.py with:
    
    1. Shebang: #!/usr/bin/env python3
    2. Import asyncio, logging, sys
    3. Configure logging:
       - Level: INFO
       - Format: "%(asctime)s [%(levelname)s] %(message)s"
       - Handlers: FileHandler(scripts/daily_job.log) + StreamHandler()
    4. main() async function:
       - Log script start
       - Import daily_market_data_job from src.scheduler.daily_job
       - Run: await daily_market_data_job()
       - Log success or catch exceptions and log error
       - Return exit code (0=success, 1=error)
    5. if __name__ == "__main__": sys.exit(asyncio.run(main()))
    
    Make executable: chmod +x scripts/daily_job.py
    
    Per D-03: This script is invoked by system cron, NOT a long-running daemon.
    APScheduler provides CronTrigger for scheduling logic, but system cron triggers execution.
  </action>
  <verify>
    <automated>python scripts/daily_job.py --help 2>&1 || python scripts/daily_job.py; echo "Exit: $?"</automated>
  </verify>
  <done>
    Script runs without error; logs to both file and stdout; exit code 0 on success, 1 on error.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Checkpoint: Configure system cron job</name>
  <what-built>
    Created scripts/daily_job.py as standalone cron entry point.
    Script fetches stock list and daily data, stores in MySQL database.
  </what-built>
  <how-to-verify>
    1. Ensure script is executable: chmod +x scripts/daily_job.py
    2. Test manual execution: python scripts/daily_job.py
    3. Verify log output shows job start/completion
    4. Check database for MarketData records: 
       mysql -u root -p -e "SELECT COUNT(*) FROM stock_logic.market_data;"
    
    5. Add system cron job (user-level, not root):
       crontab -e
       Add line: 30 15 * * 1-5 cd /Users/heyecheng/Program/llm/stock_logic && /usr/bin/python3 scripts/daily_job.py >> logs/cron.log 2>&1
    
    6. Verify cron daemon is running: pgrep cron (Linux) or launchctl list | grep cron (macOS)
    
    Expected: Job runs at 15:30 on weekdays, logs to scripts/daily_job.log and logs/cron.log
  </how-to-verify>
  <resume-signal>
    Type "approved" after cron job is configured, or describe any issues encountered.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 3: Add cron documentation to .env.example and create deployment notes</name>
  <files>.env.example, .planning/phases/01-infrastructure/CRON_SETUP.md</files>
  <action>
    Update .env.example with:
    - SCHEDULER_TIMEZONE=Asia/Shanghai
    - PYTHONPATH=/Users/heyecheng/Program/llm/stock_logic (for cron environment)
    
    Create .planning/phases/01-infrastructure/CRON_SETUP.md with:
    1. Prerequisites: Python 3.10+, MySQL 8.0+, system cron
    2. Setup steps:
       - pip install -e .
       - cp .env.example .env (configure DATABASE_URL, TUSHARE_TOKEN)
       - chmod +x scripts/daily_job.py
       - Test: python scripts/daily_job.py
    3. Cron configuration:
       - crontab -e
       - Add: 30 15 * * 1-5 cd {PROJECT_ROOT} && {PYTHON} scripts/daily_job.py >> logs/cron.log 2>&1
    4. Verification:
       - Check cron status: systemctl status cron (Linux) or launchctl list (macOS)
       - Check logs: tail -f logs/cron.log
    5. Troubleshooting:
       - Job doesn't run: Check cron daemon, verify PYTHONPATH
       - Import errors: Ensure virtualenv is activated or use absolute Python path
       - Database errors: Verify MySQL connection string
  </action>
  <verify>
    <automated>test -f .planning/phases/01-infrastructure/CRON_SETUP.md && echo "OK"</automated>
  </verify>
  <done>
    CRON_SETUP.md created with complete setup instructions; .env.example updated with scheduler vars.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| System Cron → Python Script | Cron executes script with user privileges; environment variables must be set |
| Script → MySQL Database | Database credentials from env vars; connection over localhost or network |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-09 | Information Disclosure | Cron job environment | mitigate | Document in CRON_SETUP.md to set env vars in cron context; never hardcode credentials |
| T-01-10 | Denial of Service | Job failure without notification | accept | Phase 1: manual monitoring via logs; Phase 3+: alerting system |
| T-01-11 | Integrity | Duplicate data insertion | mitigate | Database unique constraints (ix_market_data_code_date) prevent duplicates |
| T-01-12 | Availability | Cron daemon not running | accept | User monitors manually in Phase 1; system-level responsibility |
</threat_model>

<verification>
- Scheduler test: python -c "from src.scheduler.daily_job import create_scheduler; s = create_scheduler(); print(len(s.get_jobs()))"
- Script test: python scripts/daily_job.py (manual execution)
- Log verification: tail -20 scripts/daily_job.log
- Database verification: python -c "from src.database.models import MarketDataModel; from src.database.connection import async_session_maker; import asyncio; async def check(): async with async_session_maker() as s: r = await s.execute(select(MarketDataModel)); print(len(r.scalars().all()))"
</verification>

<success_criteria>
1. APScheduler CronTrigger configured for 15:30 mon-fri Asia/Shanghai
2. daily_market_data_job() fetches and stores market data correctly
3. scripts/daily_job.py runs standalone and logs to file
4. System cron job documented in CRON_SETUP.md
5. Job logs execution status with timestamps
6. No Celery or Redis dependencies (per D-03)
</success_criteria>

<output>
After completion, create .planning/phases/01-infrastructure/03-03-SUMMARY.md
</output>
