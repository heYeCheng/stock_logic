---
plan_id: 02-03
phase: 2
requirement: MACRO-03
title: Monthly Refresh Scheduler
status: pending
created: 2026-04-19
---

# Plan: Monthly Refresh Scheduler

**Requirement:** MACRO-03 — 月度数据对齐与事件触发更新机制

**Dependencies:** Phase 1 (Scheduler), Phase 2 Plan 01 (Five-Dimension Scoring)

---

## Goal

Implement monthly macro data refresh scheduler that:
1. Runs on 15th of each month at 16:00 CST (after market close)
2. Fetches latest macro data and computes snapshot
3. Logs success/failure for monitoring
4. Handles event-triggered refresh (deferred to Phase 3)

---

## Tasks

### Task 1: Monthly Cron Job

**File:** `src/macro/scheduler.py`

```python
from apscheduler.triggers.cron import CronTrigger
from src.scheduler.daily_job import get_scheduler

async def refresh_macro_data():
    """Monthly macro data refresh job."""
    logger.info("Starting monthly macro data refresh")
    
    try:
        from src.macro.service import MacroService
        from datetime import date
        
        service = MacroService()
        snapshot = await service.compute_snapshot(date.today())
        
        logger.info(f"Macro snapshot computed: {snapshot.snapshot_date}")
        logger.info(f"Composite score: {snapshot.composite_score}")
        logger.info(f"Quadrant: {snapshot.quadrant}")
        logger.info(f"Macro multiplier: {snapshot.macro_multiplier}")
        
    except Exception as e:
        logger.error(f"Macro refresh failed: {e}", exc_info=True)
        # Graceful degradation: don't crash, log error
        raise

def create_macro_scheduler():
    """Create APScheduler with monthly cron trigger."""
    scheduler = get_scheduler()
    
    # 15th of each month, 16:00 CST (Asia/Shanghai)
    trigger = CronTrigger(
        minute=0,
        hour=16,
        day=15,
        month='*',
        timezone='Asia/Shanghai'
    )
    
    scheduler.add_job(
        refresh_macro_data,
        trigger=trigger,
        id='macro_monthly_refresh',
        name='Monthly Macro Data Refresh',
        replace_existing=True
    )
    
    return scheduler
```

---

### Task 2: Integration with Daily Job

**File:** `scripts/daily_job.py` (update)

Add macro scheduler initialization:

```python
async def main() -> int:
    """Run daily job script started"""
    logger.info("=" * 50)
    logger.info("Daily job script started")
    logger.info(f"Python: {sys.version}")
    logger.info("=" * 50)
    
    try:
        from src.scheduler.daily_job import daily_market_data_job
        from src.macro.scheduler import create_macro_scheduler
        
        # Initialize macro scheduler (runs monthly)
        scheduler = create_macro_scheduler()
        scheduler.start()
        logger.info("Macro scheduler initialized (monthly refresh)")
        
        # Run daily job
        await daily_market_data_job()
        
        logger.info("Daily job completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Daily job failed: {e}", exc_info=True)
        return 1
```

---

### Task 3: Manual Trigger Endpoint

**File:** `src/macro/scheduler.py` (add)

```python
async def trigger_manual_refresh() -> dict:
    """
    Manually trigger macro data refresh.
    For admin use or testing.
    
    Returns:
        dict with status and snapshot summary
    """
    from src.macro.service import MacroService
    from datetime import date
    
    service = MacroService()
    snapshot = await service.compute_snapshot(date.today())
    
    return {
        "status": "success",
        "snapshot_date": str(snapshot.snapshot_date),
        "composite_score": float(snapshot.composite_score),
        "quadrant": snapshot.quadrant.value,
        "macro_multiplier": float(snapshot.macro_multiplier)
    }
```

---

### Task 4: Event-Triggered Refresh (Stub)

**File:** `src/macro/scheduler.py` (add stub)

```python
async def trigger_event_refresh(event_type: str, event_data: dict):
    """
    Event-triggered macro refresh.
    
    Supported events (Phase 3+):
    - policy_announcement: PBOC policy change
    - data_revision: NBS revises historical data
    - global_shock: Fed rate decision, geopolitical event
    
    Phase 2: Stub - logs event, no action
    Phase 3: Implement NLP-based policy detection
    """
    logger.info(f"Event-triggered refresh received: {event_type}")
    logger.debug(f"Event data: {event_data}")
    
    # Phase 2: No-op, just log
    # Phase 3: Implement event detection and refresh logic
```

---

### Task 5: Logging & Monitoring

**File:** `src/logging/app_logger.py` (already configured)

Macro refresh logs will use existing structured logging:

```json
{"timestamp": "2026-04-19T16:00:00.123456", "level": "INFO", "logger": "macro_scheduler", "message": "Starting monthly macro data refresh", "extra": {}}
{"timestamp": "2026-04-19T16:00:05.654321", "level": "INFO", "logger": "macro_scheduler", "message": "Macro snapshot computed", "extra": {"snapshot_date": "2026-04-15", "composite_score": 0.35, "quadrant": "wide-wide", "macro_multiplier": 1.05}}
```

**Query macro refresh history:**
```bash
# Find all macro refresh events
grep "macro" logs/app.log

# Find failed refreshes
grep "Macro refresh failed" logs/app.log

# Extract composite scores over time
grep "Composite score" logs/app.log | jq -r '.extra.composite_score'
```

---

### Task 6: Unit Tests

**File:** `tests/macro/test_scheduler.py`

```python
def test_cron_trigger_configuration():
    """Verify cron trigger is configured correctly."""
    scheduler = create_macro_scheduler()
    job = scheduler.get_job('macro_monthly_refresh')
    
    assert job is not None
    # Verify cron expression: 0 16 15 * *
    assert job.trigger.minute == 0
    assert job.trigger.hour == 16
    assert job.trigger.day == 15

async def test_manual_refresh():
    """Test manual refresh endpoint."""
    result = await trigger_manual_refresh()
    
    assert result['status'] == 'success'
    assert 'composite_score' in result
    assert 'macro_multiplier' in result
```

---

## Verification

```bash
# Run tests
python -m pytest tests/macro/test_scheduler.py -v

# Manual verification (check scheduler initialization)
python -c "
from src.macro.scheduler import create_macro_scheduler

scheduler = create_macro_scheduler()
job = scheduler.get_job('macro_monthly_refresh')

print(f'Job ID: {job.id}')
print(f'Job Name: {job.name}')
print(f'Trigger: {job.trigger}')
print(f'Next Run: {job.next_run_time}')
"

# Verify cron expression
echo "Expected: 15th of each month, 16:00 CST"
```

---

## Definition of Done

- [ ] Monthly cron job configured (15th, 16:00 CST)
- [ ] Macro refresh integrates with daily job script
- [ ] Manual trigger endpoint working
- [ ] Event-triggered stub in place
- [ ] Structured logging for monitoring
- [ ] Tests pass

---

## Risks

| Risk | Mitigation |
|------|------------|
| Macro data not ready on 15th | Graceful degradation, use prior month |
| Scheduler conflicts with daily job | Different job IDs, separate triggers |
| Timezone misconfiguration | Explicit 'Asia/Shanghai' timezone |

---

*Plan created: 2026-04-19*
