---
plan_id: LOGIC-03
phase: 3
requirement: LOGIC-03
title: Event Scorecard Rule Engine
description: Implement deterministic scoring rules for events (加减分，decay, validity)
type: feature
estimated_effort: 2h
---

# Plan: LOGIC-03 - Event Scorecard Rule Engine

## Goal
Implement deterministic event scoring rules that replace LLM subjective scoring, ensuring interpretability and backtestability.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md (LOGIC-03 section)
- Models: src/logic/models.py (EventModel, LogicModel)
- Event source: src/logic/event_extractor.py (LOGIC-02 output)

## Scoring Pipeline

```
Event (strength_raw: 0.85)
    ↓
Apply Importance Multiplier (high=1.5, medium=1.0, low=0.5)
    ↓
strength_adjusted = 0.85 × 1.5 = 1.275 (capped at 1.0)
    ↓
Apply Time Decay (optional, at query time)
    ↓
final_score = strength_adjusted × (1.0 - days_since / half_life)
```

## Tasks

### Task 1: Define importance multipliers
**File**: `src/logic/scorecard.py` (create)

```python
# Importance level multipliers
IMPORTANCE_MULTIPLIERS = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.5
}

# Default half-life for decay (days)
DEFAULT_HALF_LIFE = 7
```

### Task 2: Implement EventScorecard class
**File**: `src/logic/scorecard.py`

```python
class EventScorecard:
    """Apply deterministic scoring rules to events."""
    
    def __init__(self, half_life: int = DEFAULT_HALF_LIFE):
        self.half_life = half_life
    
    def apply_importance_multiplier(
        self,
        strength_raw: Decimal,
        importance_level: str
    ) -> Decimal:
        """Apply importance multiplier to raw strength."""
        multiplier = Decimal(str(IMPORTANCE_MULTIPLIERS.get(importance_level, 1.0)))
        adjusted = strength_raw * multiplier
        # Cap at 1.0
        return min(adjusted, Decimal("1.0"))
    
    def apply_time_decay(
        self,
        strength_adjusted: Decimal,
        event_date: date,
        as_of_date: date = None
    ) -> Decimal:
        """Apply natural time decay."""
        as_of_date = as_of_date or date.today()
        days_elapsed = (as_of_date - event_date).days
        
        if days_elapsed >= self.half_life:
            return Decimal("0")
        
        decay_factor = Decimal("1") - (Decimal(days_elapsed) / Decimal(self.half_life))
        return strength_adjusted * decay_factor
    
    def compute_validity_period(
        self,
        event_date: date,
        validity_days: int
    ) -> Tuple[date, date]:
        """Compute validity start and end dates."""
        return (event_date, event_date + timedelta(days=validity_days))
    
    def is_expired(
        self,
        validity_end: date,
        as_of_date: date = None
    ) -> bool:
        """Check if event has expired."""
        as_of_date = as_of_date or date.today()
        return as_of_date > validity_end
    
    def score_event(
        self,
        event: EventModel,
        logic: LogicModel,
        as_of_date: date = None
    ) -> EventScore:
        """Compute full score for an event."""
        as_of_date = as_of_date or date.today()
        
        # Step 1: Apply importance multiplier
        strength_adjusted = self.apply_importance_multiplier(
            Decimal(str(event.strength_raw)),
            logic.importance_level.value
        )
        
        # Step 2: Apply time decay
        decayed_strength = self.apply_time_decay(
            strength_adjusted,
            event.event_date,
            as_of_date
        )
        
        # Step 3: Check validity
        validity_start, validity_end = self.compute_validity_period(
            event.event_date,
            logic.validity_days
        )
        expired = self.is_expired(validity_end, as_of_date)
        
        return EventScore(
            event_id=event.event_id,
            strength_raw=Decimal(str(event.strength_raw)),
            strength_adjusted=strength_adjusted,
            decayed_strength=decayed_strength,
            validity_start=validity_start,
            validity_end=validity_end,
            is_expired=expired
        )
```

### Task 3: Create EventScore dataclass
**File**: `src/logic/scorecard.py`

```python
@dataclass
class EventScore:
    """Score computation result for an event."""
    event_id: str
    strength_raw: Decimal
    strength_adjusted: Decimal
    decayed_strength: Decimal
    validity_start: date
    validity_end: date
    is_expired: bool
```

### Task 4: Implement bulk scoring service
**File**: `src/logic/scorecard.py`

```python
class ScorecardManager:
    """Manage scoring for multiple events."""
    
    def __init__(self):
        self.scorecard = EventScorecard()
    
    async def score_events_for_logic(
        self,
        logic_id: str,
        as_of_date: date = None
    ) -> List[EventScore]:
        """Score all active events for a logic."""
        async with async_session_maker() as session:
            # Get logic
            logic = await session.get(LogicModel, logic_id)
            if not logic:
                return []
            
            # Get events
            result = await session.execute(
                select(EventModel).where(
                    EventModel.logic_id == logic_id,
                    EventModel.is_expired == False
                ).order_by(EventModel.event_date.desc())
            )
            events = result.scalars().all()
            
            # Score each event
            return [
                self.scorecard.score_event(event, logic, as_of_date)
                for event in events
            ]
    
    async def update_adjusted_strengths(
        self,
        logic_id: str,
        as_of_date: date = None
    ) -> int:
        """Update strength_adjusted in database for all events."""
        scores = await self.score_events_for_logic(logic_id, as_of_date)
        
        async with async_session_maker() as session:
            updated = 0
            for score in scores:
                event = await session.get(EventModel, score.event_id)
                if event:
                    event.strength_adjusted = score.strength_adjusted
                    event.validity_start = score.validity_start
                    event.validity_end = score.validity_end
                    event.is_expired = score.is_expired
                    updated += 1
            
            await session.commit()
            return updated
```

### Task 5: Create unit tests
**File**: `tests/test_scorecard.py`

Test cases:
- Test importance multiplier (high/medium/low)
- Test score capping at 1.0
- Test time decay calculation
- Test expiration logic
- Test validity period computation
- Test bulk scoring

## Success Criteria
- [ ] Importance multipliers applied correctly
- [ ] Time decay computed correctly
- [ ] Validity periods tracked
- [ ] Expiration flags updated
- [ ] Bulk scoring works efficiently
- [ ] Unit tests pass

## Dependencies
- LOGIC-01: Logic models (completed)
- LOGIC-02: Event extraction (completed)

## Notes
- Decay computed at query time (not stored)
- strength_adjusted stored after initial scoring
- Validity tracked per-event based on logic.validity_days
