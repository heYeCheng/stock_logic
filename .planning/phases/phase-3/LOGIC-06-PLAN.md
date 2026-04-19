---
plan_id: LOGIC-06
phase: 3
requirement: LOGIC-06
title: LLM Service Degradation Strategy
description: Implement fallback mechanism when LLM service unavailable
type: feature
estimated_effort: 1.5h
---

# Plan: LOGIC-06 - LLM Service Degradation Strategy

## Goal
Implement graceful degradation when LLM services are unavailable, using previous day's data with decay applied.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md (LOGIC-06 section)
- Models: src/logic/models.py (LLMServiceStatus enum, LogicScore fields)
- Existing: src/logic/net_thrust.py (LogicScore already stores llm_service_status, fallback_applied, fallback_reason)

## Service States

```python
class LLMServiceStatus(Enum):
    full = "full"       # All services operational
    degraded = "degraded"  # Partial functionality
    offline = "offline"    # Complete outage
```

## Fallback Logic

```python
if llm_service.status == OFFLINE:
    # Use previous day's logic_scores
    fallback_data = get_yesterday_scores(logic_id)
    if fallback_data:
        # Apply decay to stale data
        decay_factor = 0.8  # Configurable
        return fallback_data * decay_factor
    else:
        return 0.0
```

## Tasks

### Task 1: Implement LLMHealthMonitor
**File**: `src/logic/degradation.py` (create)

```python
class LLMHealthMonitor:
    """Monitor LLM service health and manage degradation states."""
    
    def __init__(self):
        self.current_status = LLMServiceStatus.full
        self.last_check = None
        self.consecutive_failures = 0
        self.failure_threshold = 3
    
    async def check_health(self, llm_client) -> LLMServiceStatus:
        """Perform health check on LLM service."""
        try:
            # Simple heartbeat: generate a trivial completion
            await llm_client.generate_text("Say hello")
            self.consecutive_failures = 0
            self.current_status = LLMServiceStatus.full
        except Exception as e:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_threshold:
                self.current_status = LLMServiceStatus.offline
            else:
                self.current_status = LLMServiceStatus.degraded
        
        self.last_check = datetime.now()
        return self.current_status
    
    def get_status(self) -> LLMServiceStatus:
        """Get current service status."""
        return self.current_status
    
    def is_available(self) -> bool:
        """Check if LLM service is available for use."""
        return self.current_status != LLMServiceStatus.offline
```

### Task 2: Implement DegradationService
**File**: `src/logic/degradation.py` (append)

```python
class DegradationService:
    """Handle fallback logic when LLM is unavailable."""
    
    # Decay factor for stale data (configurable)
    STALE_DATA_DECAY = Decimal("0.8")
    
    def __init__(self, health_monitor: LLMHealthMonitor):
        self.health_monitor = health_monitor
    
    async def get_logic_score_with_fallback(
        self,
        logic_id: str,
        target_date: date = None
    ) -> Optional[LogicScore]:
        """Get logic score, using fallback if LLM is offline."""
        target_date = target_date or date.today()
        
        # Check if LLM is available
        if self.health_monitor.is_available():
            # LLM available: return current day's score (already computed)
            return await self._get_score(logic_id, target_date)
        else:
            # LLM offline: use fallback
            return await self._get_fallback_score(logic_id, target_date)
    
    async def _get_score(
        self,
        logic_id: str,
        target_date: date
    ) -> Optional[LogicScore]:
        """Get score for specific date."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.logic_id == logic_id,
                    LogicScore.snapshot_date == target_date
                )
            )
            return result.scalar_one_or_none()
    
    async def _get_fallback_score(
        self,
        logic_id: str,
        target_date: date
    ) -> Optional[LogicScore]:
        """Get fallback score using previous day's data with decay."""
        # Find most recent score before target_date
        async with async_session_maker() as session:
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.logic_id == logic_id,
                    LogicScore.snapshot_date < target_date
                ).order_by(LogicScore.snapshot_date.desc())
            )
            last_score = result.scalar_one_or_none()
            
            if not last_score:
                return None
            
            # Apply decay
            days_stale = (target_date - last_score.snapshot_date).days
            decay_multiplier = self.STALE_DATA_DECAY ** days_stale
            
            # Create fallback score record
            fallback = LogicScore(
                logic_id=logic_id,
                snapshot_date=target_date,
                raw_score=last_score.raw_score * decay_multiplier,
                decayed_score=last_score.decayed_score * decay_multiplier,
                net_thrust=last_score.net_thrust * decay_multiplier,
                has_anti_logic=last_score.has_anti_logic,
                event_count=0,  # No new events
                positive_event_count=0,
                negative_event_count=0,
                llm_service_status=self.health_monitor.get_status(),
                fallback_applied=True,
                fallback_reason=f"LLM offline, using {last_score.snapshot_date} data with {days_stale}d decay"
            )
            
            session.add(fallback)
            await session.commit()
            
            return fallback
```

### Task 3: Add health check scheduler
**File**: `src/scheduler/jobs.py` (append)

```python
async def check_llm_health():
    """Check LLM service health every 5 minutes."""
    from src.llm.client import get_llm_client
    
    monitor = LLMHealthMonitor()
    llm_client = get_llm_client()
    
    await monitor.check_health(llm_client)
    
    logger.info(f"LLM health check: {monitor.get_status().value}")

# Schedule health check every 5 minutes
scheduler.add_job(
    check_llm_health,
    trigger='interval',
    minutes=5,
    id='llm_health_check',
    name='Check LLM service health'
)
```

### Task 4: Update LogicScore on snapshot generation
**File**: `src/logic/net_thrust.py` (modify _persist_snapshots)

Add llm_service_status tracking when persisting snapshots:

```python
logic_score = LogicScore(
    ...
    llm_service_status=LLMServiceStatus.full,  # Or from health monitor
    fallback_applied=False,
    fallback_reason=None
)
```

### Task 5: Create unit tests
**File**: `tests/test_degradation.py`

Test cases:
- Test health check (success path)
- Test health check (failure path)
- Test status transitions (full → degraded → offline)
- Test fallback score computation
- Test decay application for stale data
- Test no fallback when no historical data
- Test fallback_reason logging

## Success Criteria
- [ ] LLM health monitor detects service outages
- [ ] Status transitions work correctly
- [ ] Fallback scores computed with decay
- [ ] Health check runs every 5 minutes
- [ ] Fallback records include reason
- [ ] Unit tests pass

## Dependencies
- LOGIC-05: Net thrust calculation (completed)
- INFRA-04: LLM client (completed)
- INFRA-03: Scheduler (completed)

## Notes
- Fallback data marked with `fallback_applied=True`
- Downstream layers can filter/weight fallback scores
- Decay factor (0.8) is configurable
