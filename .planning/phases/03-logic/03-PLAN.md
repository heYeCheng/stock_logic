# Plan: LOGIC-03 — Event Scorecard Rule Engine

**Phase:** 3 (Logic Layer)  
**Requirement:** LOGIC-03  
**Created:** 2026-04-19  
**Status:** Ready for execution

---

## Goal

Implement event scorecard rule engine that:
1. Applies加减分 rules to events
2. Computes natural decay over time
3. Tracks validity periods
4. Outputs adjusted strength scores

---

## Scope

**In scope:**
- Scorecard class with event collection
- Daily decay application (configurable rate)
- Validity period enforcement
- Importance multiplier application
- Score persistence to database

**Out of scope:**
- Fingerprint validation (LOGIC-04)
- Net thrust calculation (LOGIC-05)
- LLM degradation (LOGIC-06)

---

## Implementation Plan

### 1. Configuration (`config/logic_scorecard.yaml`)

```yaml
# Event Scorecard Configuration

scoring:
  importance_multipliers:
    high: 1.5
    medium: 1.0
    low: 0.5
  
  decay:
    daily_rate: 0.95      # 5% daily decay
    half_life_days: 14    # ~14 days to 50%
    min_score: 0.01       # Floor to prevent negative scores
  
  validity:
    default_days: 30
    by_family:
      technology: 45      # Tech logics last longer
      policy: 60          # Policy logics last longest
      earnings: 21        # Earnings fade quickly
      m_a: 30
      supply_chain: 30
  
  thresholds:
    confidence_min: 0.6   # Reject LLM confidence < 0.6
    strength_min: 0.1     # Ignore very weak events
    strength_max: 1.0     # Cap maximum strength
```

### 2. Scorecard Model (`src/logic/scorecard.py`)

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict
from decimal import Decimal

@dataclass
class ScorecardEvent:
    """Event in scorecard with computed fields"""
    event_id: str
    logic_id: str
    event_date: date
    strength_raw: Decimal
    direction: str  # positive/negative
    importance_level: str  # high/medium/low
    validity_days: int
    created_at: date = field(default_factory=date.today)
    
    # Computed fields
    strength_adjusted: Decimal = field(default=Decimal("0"))
    decay_factor: Decimal = field(default=Decimal("1"))
    is_valid: bool = field(default=True)
    days_elapsed: int = field(default=0)

class EventScorecard:
    """Scorecard for a single logic_id"""
    
    def __init__(
        self, 
        logic_id: str,
        config: ScorecardConfig,
        importance_multipliers: Dict[str, Decimal]
    ):
        self.logic_id = logic_id
        self.config = config
        self.importance_multipliers = importance_multipliers
        self.events: List[ScorecardEvent] = []
        self.current_score: Decimal = Decimal("0")
        self.last_updated: date = date.today()
    
    def add_event(self, event: ScorecardEvent) -> None:
        """Add event to scorecard with validation"""
        
        # Validate confidence threshold
        if event.confidence < self.config.thresholds.confidence_min:
            logger.debug(f"Event {event.event_id} confidence too low, rejecting")
            return
        
        # Validate strength threshold
        if event.strength_raw < self.config.thresholds.strength_min:
            logger.debug(f"Event {event.event_id} strength too low, rejecting")
            return
        
        # Apply importance multiplier
        multiplier = self.importance_multipliers.get(event.importance_level, Decimal("1.0"))
        event.strength_adjusted = event.strength_raw * multiplier
        
        # Cap at max
        if event.strength_adjusted > self.config.thresholds.strength_max:
            event.strength_adjusted = Decimal(str(self.config.thresholds.strength_max))
        
        self.events.append(event)
        self._recalculate_score()
    
    def apply_decay(self, target_date: date = None) -> None:
        """Apply natural decay to all events"""
        target_date = target_date or date.today()
        days_elapsed = (target_date - self.last_updated).days
        
        if days_elapsed <= 0:
            return
        
        logger.debug(f"Applying {days_elapsed} days decay to scorecard {self.logic_id}")
        
        # Apply decay factor: score *= decay_rate ^ days
        decay_multiplier = Decimal(str(self.config.decay.daily_rate)) ** days_elapsed
        
        for event in self.events:
            event.days_elapsed += days_elapsed
            event.decay_factor = decay_multiplier
            
            # Check validity
            if event.days_elapsed > event.validity_days:
                event.is_valid = False
        
        self._recalculate_score()
        self.last_updated = target_date
    
    def _recalculate_score(self) -> None:
        """Recalculate current score from valid events"""
        valid_events = [e for e in self.events if e.is_valid]
        
        self.current_score = sum(
            e.strength_adjusted * e.decay_factor 
            for e in valid_events
        )
    
    def get_summary(self) -> ScorecardSummary:
        """Get scorecard summary"""
        valid_events = [e for e in self.events if e.is_valid]
        expired_events = [e for e in self.events if not e.is_valid]
        
        return ScorecardSummary(
            logic_id=self.logic_id,
            current_score=self.current_score,
            event_count=len(valid_events),
            expired_count=len(expired_events),
            last_updated=self.last_updated
        )
```

### 3. Scorecard Manager (`src/logic/scorecard_manager.py`)

```python
class ScorecardManager:
    """Manage scorecards for all logics"""
    
    def __init__(self, config_path: str = "config/logic_scorecard.yaml"):
        self.config = self._load_config(config_path)
        self.scorecards: Dict[str, EventScorecard] = {}
    
    def get_or_create_scorecard(self, logic_id: str) -> EventScorecard:
        """Get existing scorecard or create new one"""
        if logic_id not in self.scorecards:
            self.scorecards[logic_id] = EventScorecard(
                logic_id=logic_id,
                config=self.config
            )
        return self.scorecards[logic_id]
    
    def process_daily_snapshot(self, snapshot_date: date) -> Dict[str, Decimal]:
        """
        Process daily snapshot:
        1. Apply decay to all scorecards
        2. Remove expired events
        3. Return scores for persistence
        """
        scores = {}
        
        for logic_id, scorecard in self.scorecards.items():
            scorecard.apply_decay(snapshot_date)
            summary = scorecard.get_summary()
            scores[logic_id] = summary.current_score
        
        return scores
    
    async def persist_scores(
        self, 
        scores: Dict[str, Decimal], 
        snapshot_date: date
    ) -> None:
        """Persist scores to logic_scores table"""
        async with async_session_maker() as session:
            for logic_id, score in scores.items():
                logic_score = LogicScore(
                    logic_id=logic_id,
                    snapshot_date=snapshot_date,
                    raw_score=score,
                    decayed_score=score,  # Already decayed
                    event_count=len(self.scorecards[logic_id].events)
                )
                
                # Upsert
                existing = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == logic_id,
                        LogicScore.snapshot_date == snapshot_date
                    )
                )
                existing = existing.scalar_one_or_none()
                
                if existing:
                    existing.raw_score = score
                    existing.decayed_score = score
                else:
                    session.add(logic_score)
            
            await session.commit()
```

### 4. Integration Test

```python
async def test_scorecard_decay():
    """Test scorecard decay over time"""
    
    config = ScorecardConfig(
        decay={"daily_rate": 0.95},
        importance_multipliers={"high": Decimal("1.5")}
    )
    
    scorecard = EventScorecard("test_logic", config)
    
    # Add event
    event = ScorecardEvent(
        event_id="test_001",
        logic_id="test_logic",
        event_date=date.today(),
        strength_raw=Decimal("0.8"),
        importance_level="high",
        validity_days=30
    )
    
    scorecard.add_event(event)
    assert scorecard.current_score == Decimal("0.8") * Decimal("1.5")  # 1.2
    
    # Apply 7 days decay
    future_date = date.today() + timedelta(days=7)
    scorecard.apply_decay(future_date)
    
    # Score should be ~1.2 * 0.95^7 ≈ 0.84
    expected = Decimal("1.2") * (Decimal("0.95") ** 7)
    assert abs(scorecard.current_score - expected) < Decimal("0.01")
    
    # Apply 35 days decay (past validity)
    far_future = date.today() + timedelta(days=35)
    scorecard.apply_decay(far_future)
    
    # Event should be expired, score = 0
    assert scorecard.current_score == 0
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `config/logic_scorecard.yaml` | Create | Scorecard configuration |
| `src/logic/scorecard.py` | Create | EventScorecard class |
| `src/logic/scorecard_manager.py` | Create | Scorecard manager |
| `src/logic/models.py` | Modify | Add LogicScore ORM model |
| `tests/logic/test_scorecard.py` | Create | Unit tests for scorecard |
| `alembic/versions/xxx_logic_scores_table.py` | Create | Migration for logic_scores table |

---

## Dependencies

- LOGIC-01: Logic identification (provides logic schema)
- LOGIC-02: Event extraction (provides events)
- Phase 1: Database layer, configuration module

---

## Success Criteria

1. ✅ `logic_scores` table created with proper schema
2. ✅ Importance multipliers correctly applied (high=1.5, medium=1.0, low=0.5)
3. ✅ Daily decay computed correctly (0.95^days)
4. ✅ Events marked expired after validity_days
5. ✅ Expired events excluded from score calculation
6. ✅ Scores persisted to database daily
7. ✅ Configuration loaded from YAML file

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Decay rate too aggressive | Scores drop to zero too fast | Make configurable, test with backtesting |
| Floating point precision | Score drift over time | Use Decimal for all calculations |
| Validity boundary errors | Off-by-one in days calculation | Use inclusive counting, test edge cases |
| Memory leak | Scorecards accumulate indefinitely | Prune scorecards with no valid events |

---

## Execution Notes

- Use `Decimal` for all score calculations (no floats)
- Load config from YAML at startup
- Log decay application for auditing
- Test with edge cases (0 days, exactly validity_days, > validity_days)

---

*Plan created: 2026-04-19*
