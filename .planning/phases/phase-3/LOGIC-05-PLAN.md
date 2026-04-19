---
plan_id: LOGIC-05
phase: 3
requirement: LOGIC-05
title: Net Thrust Calculation
description: Aggregate positive/negative events with anti-logic flagging
type: feature
estimated_effort: 1.5h
---

# Plan: LOGIC-05 - Net Thrust Calculation

## Goal
Implement net thrust calculation that aggregates positive and negative events per logic, with anti-logic flagging for conflicting signals.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md (LOGIC-05 section)
- Models: src/logic/models.py (LogicScore, EventModel)
- Existing: src/logic/net_thrust.py (already implemented, verified functional)

## Calculation Formula

```python
positive_strength = sum(e.strength_adjusted for e in positive_events)
negative_strength = sum(e.strength_adjusted for e in negative_events)
net_thrust = positive_strength - negative_strength
has_anti_logic = (positive_strength > 0 and negative_strength > 0)
```

## Tasks

### Task 1: Verify existing NetThrustCalculator
**File**: `src/logic/net_thrust.py` (already exists)

Verify the existing implementation:
- [ ] `NetThrustCalculator.calculate()` method works correctly
- [ ] Separates positive/negative events
- [ ] Computes strength sums correctly
- [ ] Sets `has_anti_logic` flag properly
- [ ] Returns `NetThrustResult` dataclass

### Task 2: Verify LogicSnapshotService
**File**: `src/logic/net_thrust.py` (already exists)

Verify the existing service:
- [ ] `generate_daily_snapshot()` fetches active logics
- [ ] Gets valid events per logic
- [ ] Calculates net thrust
- [ ] Persists to `logic_scores` table
- [ ] Handles updates vs inserts correctly

### Task 3: Add daily scheduler integration
**File**: `src/scheduler/jobs.py` (create or modify)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.logic.net_thrust import LogicSnapshotService

scheduler = AsyncIOScheduler()

async def run_daily_logic_snapshot():
    """Generate daily logic score snapshots."""
    service = LogicSnapshotService()
    await service.generate_daily_snapshot(date.today())

# Schedule daily at 16:30 (after market close)
scheduler.add_job(
    run_daily_logic_snapshot,
    trigger='cron',
    hour=16,
    minute=30,
    id='daily_logic_snapshot',
    name='Generate daily logic score snapshots'
)
```

### Task 4: Add query interface for downstream layers
**File**: `src/logic/net_thrust.py` (verify LogicScoreQueries exists)

Verify these query methods exist:
- [ ] `get_latest_scores()` - Returns dict of logic_id → net_thrust
- [ ] `get_anti_logic_flags()` - Returns list of logic_ids with anti-logic

### Task 5: Create unit tests
**File**: `tests/test_net_thrust.py`

Test cases:
- Test net thrust calculation (positive only)
- Test net thrust calculation (negative only)
- Test net thrust calculation (mixed, anti-logic)
- Test anti-logic flag triggering
- Test snapshot persistence
- Test snapshot update vs insert
- Test query methods

## Success Criteria
- [ ] NetThrustCalculator computes correct values
- [ ] LogicSnapshotService generates daily snapshots
- [ ] Scheduler runs daily at 16:30
- [ ] Anti-logic flag set correctly
- [ ] Query methods return correct data
- [ ] Unit tests pass

## Dependencies
- LOGIC-02: Event extraction (completed)
- LOGIC-03: Scorecard (completed)
- LOGIC-04: Fingerprint (completed)
- INFRA-03: Scheduler (completed in Phase 1)

## Notes
- Net thrust is the primary output for downstream layers
- Anti-logic flag indicates conflicting signals (reduce position)
- Snapshots stored for historical analysis and backtesting
