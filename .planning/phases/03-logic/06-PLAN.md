# Plan: LOGIC-06 — LLM Service Degradation Strategy

**Phase:** 3 (Logic Layer)  
**Requirement:** LOGIC-06  
**Created:** 2026-04-19  
**Status:** Ready for execution

---

## Goal

Implement LLM service degradation strategy that:
1. Detects LLM service availability and health
2. Falls back to previous day's scores with decay when LLM unavailable
3. Logs degradation status for monitoring
4. Gracefully recovers when service restored

---

## Scope

**In scope:**
- LLM health check mechanism
- Three-level degradation states (full, degraded, offline)
- Fallback score computation (prior day × decay)
- Status persistence to `logic_scores` table
- Recovery logic when service restored

**Out of scope:**
- Logic identification (LOGIC-01)
- Event extraction (LOGIC-02)
- Scorecard rules (LOGIC-03)
- Net thrust calculation (LOGIC-05)

---

## Implementation Plan

### 1. Degradation State Enum (`src/logic/models.py`)

```python
class LLMServiceStatus(Enum):
    """LLM service health status"""
    FULL = "full"          # Normal operation, all features available
    DEGRADED = "degraded"  # Slow responses, rate limited, reduced features
    OFFLINE = "offline"    # Unavailable, using fallback

class LogicScore(Base):
    __tablename__ = "logic_scores"
    
    # ... existing fields ...
    
    # LLM service status
    llm_service_status = Column(Enum(LLMServiceStatus), default=LLMServiceStatus.FULL)
    fallback_applied = Column(Boolean, default=False)
    fallback_reason = Column(String(200), nullable=True)
```

### 2. LLM Health Monitor (`src/logic/llm_health.py`)

```python
import asyncio
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
from litellm import acompletion

class LLMHealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class LLMHealthMonitor:
    """Monitor LLM service health"""
    
    # Health check configuration
    HEALTH_CHECK_TIMEOUT = 10  # seconds
    HEALTH_CHECK_INTERVAL = 60  # seconds
    FAILURE_THRESHOLD = 3  # Consecutive failures before marking unhealthy
    RECOVERY_THRESHOLD = 2  # Consecutive successes before marking healthy
    
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check_time: Optional[datetime] = None
        self.last_successful_check: Optional[datetime] = None
        self.current_status = LLMHealthStatus.HEALTHY
    
    async def check_health(self) -> LLMHealthStatus:
        """
        Check LLM service health with simple probe
        
        Returns:
            LLMHealthStatus indicating service health
        """
        try:
            start_time = datetime.now()
            
            # Simple probe: echo test
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Respond with exactly: OK"}
                ],
                max_tokens=5,
                timeout=self.HEALTH_CHECK_TIMEOUT
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Check response
            content = response.choices[0].message.content.strip()
            if "OK" not in content:
                raise ValueError(f"Unexpected response: {content}")
            
            # Record success
            self.consecutive_failures = 0
            self.consecutive_successes += 1
            self.last_successful_check = datetime.now()
            
            # Determine status based on response time
            if elapsed > 5.0:  # Slow but acceptable
                self.current_status = LLMHealthStatus.DEGRADED
            elif self.consecutive_successes >= self.RECOVERY_THRESHOLD:
                self.current_status = LLMHealthStatus.HEALTHY
            
            self.last_check_time = datetime.now()
            return self.current_status
            
        except Exception as e:
            self.consecutive_successes = 0
            self.consecutive_failures += 1
            self.last_check_time = datetime.now()
            
            if self.consecutive_failures >= self.FAILURE_THRESHOLD:
                self.current_status = LLMHealthStatus.UNHEALTHY
            
            logger.warning(f"LLM health check failed: {e}")
            return self.current_status
    
    def get_status(self) -> LLMHealthStatus:
        """Get current health status without checking"""
        return self.current_status
    
    def is_available(self) -> bool:
        """Check if LLM is available for normal processing"""
        return self.current_status != LLMHealthStatus.UNHEALTHY
    
    def get_status_string(self) -> str:
        """Get status string for logging"""
        return f"{self.current_status.value} (failures={self.consecutive_failures}, successes={self.consecutive_successes})"
```

### 3. Degradation Service (`src/logic/degradation_service.py`)

```python
from decimal import Decimal
from datetime import date, timedelta

class DegradationService:
    """Handle LLM degradation fallback logic"""
    
    DECAY_RATE = Decimal("0.9")  # 10% daily decay for fallback
    
    def __init__(self):
        self.health_monitor = LLMHealthMonitor()
    
    async def get_logic_scores(
        self, 
        target_date: date,
        llm_processor: Callable
    ) -> Tuple[Dict[str, Decimal], LLMServiceStatus]:
        """
        Get logic scores with degradation handling
        
        Args:
            target_date: Date for scores
            llm_processor: Async callable that processes news and returns scores
        
        Returns:
            (scores, status) tuple
            - scores: Dict[logic_id, net_thrust]
            - status: LLMServiceStatus indicating processing mode
        """
        # Check health
        health = await self.health_monitor.check_health()
        
        if health == LLMHealthStatus.HEALTHY:
            # Normal processing
            try:
                scores = await llm_processor(target_date)
                return scores, LLMServiceStatus.FULL
            except Exception as e:
                logger.error(f"LLM processing failed: {e}")
                # Fall through to degraded/offline handling
                health = await self.health_monitor.check_health()
        
        if health == LLMHealthStatus.DEGRADED:
            # Degraded: try with reduced batch size or timeout
            logger.warning("LLM degraded, attempting reduced processing")
            try:
                scores = await llm_processor(target_date, reduced_mode=True)
                return scores, LLMServiceStatus.DEGRADED
            except Exception as e:
                logger.error(f"Reduced processing failed: {e}")
                # Fall through to offline
                pass
        
        # Offline: use fallback
        logger.warning("LLM offline, using fallback scores")
        fallback_scores = await self._get_fallback_scores(target_date)
        return fallback_scores, LLMServiceStatus.OFFLINE
    
    async def _get_fallback_scores(self, target_date: date) -> Dict[str, Decimal]:
        """
        Get fallback scores from prior day with decay
        
        Fallback logic:
        1. Fetch yesterday's logic_scores
        2. Apply 10% decay
        3. Return as fallback
        """
        prior_date = target_date - timedelta(days=1)
        
        async with async_session_maker() as session:
            # Fetch prior day scores
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.snapshot_date == prior_date
                )
            )
            prior_scores = result.scalars().all()
            
            if not prior_scores:
                logger.warning(f"No prior scores for {prior_date}, using zeros")
                return {}
            
            # Apply decay
            fallback = {}
            for ps in prior_scores:
                decayed = ps.net_thrust * self.DECAY_RATE
                fallback[ps.logic_id] = decayed
            
            logger.info(
                f"Fallback scores computed: {len(fallback)} logics, "
                f"decay={self.DECAY_RATE}"
            )
            
            return fallback
    
    async def persist_fallback_metadata(
        self, 
        scores: Dict[str, Decimal],
        snapshot_date: date,
        status: LLMServiceStatus
    ) -> None:
        """Persist fallback metadata for auditing"""
        async with async_session_maker() as session:
            for logic_id, score in scores.items():
                # Check if record exists
                existing = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == logic_id,
                        LogicScore.snapshot_date == snapshot_date
                    )
                )
                existing = existing.scalar_one_or_none()
                
                if existing:
                    existing.llm_service_status = status
                    existing.fallback_applied = (status != LLMServiceStatus.FULL)
                    existing.fallback_reason = f"LLM {status.value} at {datetime.now()}"
                else:
                    # Create new record for fallback
                    logic_score = LogicScore(
                        logic_id=logic_id,
                        snapshot_date=snapshot_date,
                        net_thrust=score,
                        llm_service_status=status,
                        fallback_applied=(status != LLMServiceStatus.FULL),
                        fallback_reason=f"LLM {status.value} at {datetime.now()}"
                    )
                    session.add(logic_score)
            
            await session.commit()
```

### 4. Integration with Daily Job (`src/logic/scheduler.py`)

```python
class LogicDailyJob:
    """Daily logic layer batch job"""
    
    def __init__(self):
        self.degradation_service = DegradationService()
        self.batch_processor = EventBatchProcessor()
        self.snapshot_service = LogicSnapshotService()
    
    async def run(self, run_date: date = None) -> None:
        """
        Run daily logic layer processing
        
        1. Fetch news articles
        2. Process through LLM pipeline
        3. Generate snapshots
        4. Handle degradation
        """
        run_date = run_date or date.today()
        logger.info(f"Starting daily logic job for {run_date}")
        
        # Fetch news
        news_articles = await self._fetch_news(run_date)
        
        # Define processor
        async def process_news(date, reduced_mode=False):
            if reduced_mode:
                # Process only high-importance articles
                news_articles = [a for a in news_articles if a.get("importance") == "high"]
            
            result = await self.batch_processor.process_batch(news_articles)
            scores = await self.snapshot_service.generate_daily_snapshot(date)
            return {s.logic_id: s.net_thrust for s in scores}
        
        # Process with degradation handling
        scores, status = await self.degradation_service.get_logic_scores(
            run_date,
            process_news
        )
        
        # Persist metadata
        await self.degradation_service.persist_fallback_metadata(
            scores, run_date, status
        )
        
        logger.info(
            f"Daily logic job complete: status={status.value}, "
            f"logics={len(scores)}"
        )
```

### 5. Integration Test

```python
async def test_degradation_fallback():
    """Test fallback when LLM offline"""
    
    degradation_service = DegradationService()
    
    # Setup: Create prior day scores
    await self._seed_prior_scores()
    
    # Simulate LLM failure
    async def failing_processor(date, reduced_mode=False):
        raise Exception("LLM service unavailable")
    
    # Get scores (should fallback)
    scores, status = await degradation_service.get_logic_scores(
        date.today(),
        failing_processor
    )
    
    assert status == LLMServiceStatus.OFFLINE
    assert len(scores) > 0  # Should have fallback scores
    assert all(s.net_thrust * Decimal("0.9") for s in scores.values())  # Decayed
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/logic/llm_health.py` | Create | LLM health monitor |
| `src/logic/degradation_service.py` | Create | Degradation handling |
| `src/logic/models.py` | Modify | Add LLMServiceStatus enum, fields |
| `src/logic/scheduler.py` | Modify | Integrate degradation into daily job |
| `tests/logic/test_degradation.py` | Create | Unit tests for degradation |
| `alembic/versions/xxx_add_llm_status_fields.py` | Create | Migration for status fields |

---

## Dependencies

- LOGIC-05: Net thrust (provides score baseline)
- Phase 1: LiteLLM integration, scheduler
- Phase 2: None (independent)

---

## Success Criteria

1. ✅ LLM health check detects service failures
2. ✅ Three degradation states correctly transitioned
3. ✅ Fallback scores computed (prior day × 0.9 decay)
4. ✅ Fallback metadata persisted for auditing
5. ✅ Daily job integrates degradation handling
6. ✅ Recovery works when service restored

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positive failures | Unnecessary fallback | Use 3 consecutive failures threshold |
| Fallback decay too aggressive | Scores drop too fast | Tune decay rate (0.9 = 10% daily) |
| No prior scores available | Fallback returns zeros | Log warning, continue with zeros |
| Health check adds latency | Slower processing | Run health check asynchronously |

---

## Execution Notes

- Health check runs before each batch processing
- Fallback is per-batch, not per-logic
- Monitor fallback frequency in production
- Consider multi-model fallback (Claude → GPT) in future

---

*Plan created: 2026-04-19*
