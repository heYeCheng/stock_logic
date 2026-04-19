# Plan: LOGIC-05 — Net Thrust Calculation

**Phase:** 3 (Logic Layer)  
**Requirement:** LOGIC-05  
**Created:** 2026-04-19  
**Status:** Ready for execution

---

## Goal

Implement net thrust calculation that:
1. Aggregates positive and negative event strengths per logic_id
2. Computes net thrust (positive - negative)
3. Flags logics with conflicting signals (anti-logic)
4. Outputs daily snapshot for downstream consumption

---

## Scope

**In scope:**
- Net thrust computation algorithm
- Anti-logic flagging logic
- Daily snapshot persistence
- Query interface for downstream layers
- Score aggregation by logic_family

**Out of scope:**
- Event extraction (LOGIC-02)
- Scoring rules (LOGIC-03)
- Fingerprint validation (LOGIC-04)
- Macro multiplier application (Phase 2, used in Phase 5)

---

## Implementation Plan

### 1. Net Thrust Calculator (`src/logic/net_thrust.py`)

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Tuple
from datetime import date

@dataclass
class NetThrustResult:
    """Net thrust calculation result"""
    logic_id: str
    positive_strength: Decimal  # Sum of positive events
    negative_strength: Decimal  # Sum of negative events
    net_thrust: Decimal  # positive - negative
    has_anti_logic: bool  # Both positive and negative events exist
    event_count: int
    positive_event_count: int
    negative_event_count: int
    snapshot_date: date

class NetThrustCalculator:
    """Calculate net thrust with anti-logic flagging"""
    
    def calculate(self, events: List[Event]) -> NetThrustResult:
        """
        Calculate net thrust from list of events
        
        Args:
            events: List of valid, non-expired events for a single logic_id
        
        Returns:
            NetThrustResult with all metrics
        """
        if not events:
            return NetThrustResult(
                logic_id=events[0].logic_id if events else "",
                positive_strength=Decimal("0"),
                negative_strength=Decimal("0"),
                net_thrust=Decimal("0"),
                has_anti_logic=False,
                event_count=0,
                positive_event_count=0,
                negative_event_count=0,
                snapshot_date=date.today()
            )
        
        # Separate positive and negative events
        positive_events = [e for e in events if e.direction == "positive"]
        negative_events = [e for e in events if e.direction == "negative"]
        
        # Sum strengths (already adjusted for importance and decay)
        positive_strength = sum(
            (e.strength_adjusted * e.decay_factor for e in positive_events),
            Decimal("0")
        )
        negative_strength = sum(
            (e.strength_adjusted * e.decay_factor for e in negative_events),
            Decimal("0")
        )
        
        # Net thrust
        net_thrust = positive_strength - negative_strength
        
        # Anti-logic flag: both sides have non-zero strength
        has_anti_logic = (positive_strength > 0 and negative_strength > 0)
        
        return NetThrustResult(
            logic_id=events[0].logic_id,
            positive_strength=positive_strength,
            negative_strength=negative_strength,
            net_thrust=net_thrust,
            has_anti_logic=has_anti_logic,
            event_count=len(events),
            positive_event_count=len(positive_events),
            negative_event_count=len(negative_events),
            snapshot_date=date.today()
        )
```

### 2. Daily Snapshot Service (`src/logic/snapshot_service.py`)

```python
class LogicSnapshotService:
    """Generate daily logic score snapshots"""
    
    def __init__(self):
        self.calculator = NetThrustCalculator()
        self.scorecard_manager = ScorecardManager()
    
    async def generate_daily_snapshot(self, snapshot_date: date) -> List[NetThrustResult]:
        """
        Generate daily snapshot for all active logics
        
        Steps:
        1. Fetch all active logics
        2. For each logic, get valid events
        3. Calculate net thrust
        4. Persist to logic_scores table
        
        Returns:
            List of NetThrustResult for all logics
        """
        async with async_session_maker() as session:
            # Fetch active logics
            result = await session.execute(
                select(Logic).where(Logic.is_active == True)
            )
            logics = result.scalars().all()
        
        results = []
        
        for logic in logics:
            # Get valid events for this logic
            events = await self._get_valid_events(logic.logic_id, snapshot_date)
            
            # Calculate net thrust
            thrust_result = self.calculator.calculate(events)
            results.append(thrust_result)
        
        # Persist all results
        await self._persist_snapshots(results)
        
        return results
    
    async def _get_valid_events(
        self, 
        logic_id: str, 
        snapshot_date: date
    ) -> List[Event]:
        """Get non-expired events for logic as of snapshot_date"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Event).where(
                    Event.logic_id == logic_id,
                    Event.event_date <= snapshot_date,
                    Event.is_expired == False
                ).order_by(Event.event_date.desc())
            )
            return result.scalars().all()
    
    async def _persist_snapshots(
        self, 
        results: List[NetThrustResult]
    ) -> None:
        """Persist net thrust results to logic_scores table"""
        async with async_session_maker() as session:
            for result in results:
                logic_score = LogicScore(
                    logic_id=result.logic_id,
                    snapshot_date=result.snapshot_date,
                    raw_score=result.positive_strength + result.negative_strength,
                    decayed_score=abs(result.net_thrust),
                    net_thrust=result.net_thrust,
                    has_anti_logic=result.has_anti_logic,
                    event_count=result.event_count,
                    positive_event_count=result.positive_event_count,
                    negative_event_count=result.negative_event_count,
                    llm_service_status="full"  # Updated by LOGIC-06
                )
                
                # Upsert
                existing = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == result.logic_id,
                        LogicScore.snapshot_date == result.snapshot_date
                    )
                )
                existing = existing.scalar_one_or_none()
                
                if existing:
                    # Update fields
                    for key, value in logic_score.__dict__.items():
                        if not key.startswith('_'):
                            setattr(existing, key, value)
                else:
                    session.add(logic_score)
            
            await session.commit()
```

### 3. Query Interface (`src/logic/queries.py`)

```python
class LogicScoreQueries:
    """Query interface for downstream layers"""
    
    @staticmethod
    async def get_latest_scores() -> Dict[str, Decimal]:
        """Get latest net thrust scores for all logics"""
        async with async_session_maker() as session:
            # Get max snapshot_date
            max_date_result = await session.execute(
                select(func.max(LogicScore.snapshot_date))
            )
            max_date = max_date_result.scalar()
            
            if not max_date:
                return {}
            
            # Get scores for max_date
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.snapshot_date == max_date
                )
            )
            scores = result.scalars().all()
            
            return {s.logic_id: s.net_thrust for s in scores}
    
    @staticmethod
    async def get_scores_by_family(
        snapshot_date: date = None
    ) -> Dict[str, Decimal]:
        """
        Aggregate net thrust by logic_family
        
        Useful for sector rotation decisions
        """
        snapshot_date = snapshot_date or date.today()
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(
                    Logic.logic_family,
                    func.sum(LogicScore.net_thrust).label("total_thrust")
                )
                .join(LogicScore, Logic.logic_id == LogicScore.logic_id)
                .where(LogicScore.snapshot_date == snapshot_date)
                .group_by(Logic.logic_family)
            )
            return {row.logic_family: row.total_thrust for row in result}
    
    @staticmethod
    async def get_anti_logic_flags(
        snapshot_date: date = None
    ) -> List[str]:
        """Get list of logic_ids with anti-logic flags"""
        snapshot_date = snapshot_date or date.today()
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(LogicScore.logic_id).where(
                    LogicScore.snapshot_date == snapshot_date,
                    LogicScore.has_anti_logic == True
                )
            )
            return [row.logic_id for row in result]
```

### 4. Integration Test

```python
async def test_net_thrust_calculation():
    """Test net thrust with mixed signals"""
    
    calculator = NetThrustCalculator()
    
    # Create test events
    events = [
        Event(
            event_id="pos_001",
            logic_id="tech_ai_001",
            direction="positive",
            strength_adjusted=Decimal("0.8"),
            decay_factor=Decimal("1.0"),
            event_date=date.today()
        ),
        Event(
            event_id="pos_002",
            logic_id="tech_ai_001",
            direction="positive",
            strength_adjusted=Decimal("0.6"),
            decay_factor=Decimal("0.95"),
            event_date=date.today()
        ),
        Event(
            event_id="neg_001",
            logic_id="tech_ai_001",
            direction="negative",
            strength_adjusted=Decimal("0.4"),
            decay_factor=Decimal("1.0"),
            event_date=date.today()
        )
    ]
    
    result = calculator.calculate(events)
    
    # Positive: 0.8 + 0.6*0.95 = 0.8 + 0.57 = 1.37
    # Negative: 0.4
    # Net: 1.37 - 0.4 = 0.97
    assert result.positive_strength == Decimal("1.37")
    assert result.negative_strength == Decimal("0.4")
    assert result.net_thrust == Decimal("0.97")
    assert result.has_anti_logic == True  # Both sides present
    assert result.positive_event_count == 2
    assert result.negative_event_count == 1
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/logic/net_thrust.py` | Create | Net thrust calculator |
| `src/logic/snapshot_service.py` | Create | Daily snapshot generation |
| `src/logic/queries.py` | Create | Query interface for downstream |
| `src/logic/models.py` | Modify | Add fields to LogicScore |
| `tests/logic/test_net_thrust.py` | Create | Unit tests for net thrust |
| `alembic/versions/xxx_add_net_thrust_fields.py` | Create | Migration for new fields |

---

## Dependencies

- LOGIC-03: Scorecard (provides adjusted event scores)
- LOGIC-04: Fingerprint (ensures no duplicate events)
- Phase 1: Database layer

---

## Success Criteria

1. ✅ Net thrust computed correctly (positive - negative)
2. ✅ Anti-logic flag set when both +/- events exist
3. ✅ Daily snapshot persisted to `logic_scores` table
4. ✅ Query interface returns latest scores
5. ✅ Aggregation by logic_family works correctly
6. ✅ Integration test passes with mixed signals

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Net thrust sign confusion | Positive/negative reversed | Clear documentation, unit tests |
| Anti-logic false positive | Weak signals trigger flag | Add threshold (e.g., both > 0.1) |
| Snapshot timing issues | Wrong date used | Use consistent snapshot_date parameter |
| Decimal precision errors | Score drift | Use Decimal throughout |

---

## Execution Notes

- Net thrust can be negative (more negative than positive)
- Anti-logic flag is informational, doesn't change score
- Consider adding confidence intervals in future
- Snapshot service should run after market close (15:30 CST)

---

*Plan created: 2026-04-19*
