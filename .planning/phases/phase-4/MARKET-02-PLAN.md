---
plan_id: MARKET-02
phase: 4
requirement: MARKET-02
title: Sector Three-State Determination
description: Implement weak/normal/overheated state classification with hysteresis
type: feature
estimated_effort: 1h
---

# Plan: MARKET-02 - Sector Three-State Determination

## Goal
Implement sector state classification (weak/normal/overheated) with hysteresis logic to prevent rapid state flipping.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (MARKET-02 section)
- Models: src/market/models.py (SectorScore with state field)
- Dependencies: MARKET-01 (sector radar scores)

## State Thresholds with Hysteresis

```python
class SectorState(Enum):
    weak = "weak"           # composite_score < 0.35
    normal = "normal"       # 0.35 <= composite_score <= 0.70
    overheated = "overheated"  # composite_score > 0.70
```

### Hysteresis Logic
```python
# To prevent rapid flipping, use different thresholds for transitions
TRANSITION_THRESHOLDS = {
    ("weak", "normal"): 0.40,       # Need >0.40 to go weak→normal
    ("normal", "overheated"): 0.75, # Need >0.75 to go normal→overheated
    ("overheated", "normal"): 0.65, # Need <0.65 to go overheated→normal
    ("normal", "weak"): 0.30,       # Need <0.30 to go normal→weak
}
```

## Tasks

### Task 1: Create SectorState enum
**File**: `src/market/models.py` (append)

```python
class SectorState(str, Enum):
    weak = "weak"
    normal = "normal"
    overheated = "overheated"
    
    @classmethod
    def from_composite_score(cls, score: Decimal, previous_state: Optional["SectorState"] = None) -> "SectorState":
        """Determine state with hysteresis."""
        if previous_state is None:
            # No history, use simple thresholds
            if score < Decimal("0.35"):
                return cls.weak
            elif score > Decimal("0.70"):
                return cls.overheated
            else:
                return cls.normal
        
        # Apply hysteresis
        if previous_state == cls.weak:
            return cls.normal if score > Decimal("0.40") else cls.weak
        elif previous_state == cls.overheated:
            return cls.normal if score < Decimal("0.65") else cls.overheated
        else:  # normal
            if score > Decimal("0.75"):
                return cls.overheated
            elif score < Decimal("0.30"):
                return cls.weak
            else:
                return cls.normal
```

### Task 2: Implement StateTransitionService
**File**: `src/market/state_machine.py` (create)

```python
class StateTransitionService:
    """Manage sector state transitions with hysteresis."""
    
    def __init__(self):
        self.state_history: Dict[str, List[Tuple[date, SectorState]]] = defaultdict(list)
    
    async def update_state(self, sector_id: str, snapshot: SectorScore) -> SectorState:
        """Update sector state based on composite score and history."""
        
        # Get previous state
        previous_state = await self._get_previous_state(sector_id)
        
        # Calculate new state with hysteresis
        new_state = SectorState.from_composite_score(
            snapshot.composite_score, 
            previous_state
        )
        
        # Track consecutive days
        consecutive_days = await self._calculate_consecutive_days(
            sector_id, new_state
        )
        
        # Calculate confidence (distance from boundaries)
        confidence = self._calculate_confidence(
            snapshot.composite_score, new_state
        )
        
        # Update history
        self.state_history[sector_id].append((snapshot.snapshot_date, new_state))
        
        # Persist
        await self._persist_transition(sector_id, new_state, consecutive_days, confidence)
        
        return new_state
    
    def _calculate_confidence(self, score: Decimal, state: SectorState) -> float:
        """Calculate how far score is from state boundaries."""
        if state == SectorState.weak:
            # Distance from 0.35 boundary
            return float(Decimal("0.35") - score) / Decimal("0.35")
        elif state == SectorState.overheated:
            # Distance from 0.70 boundary
            return float(score - Decimal("0.70")) / Decimal("0.30")
        else:  # normal
            # Distance from nearest boundary
            dist_to_weak = float(score - Decimal("0.35"))
            dist_to_hot = float(Decimal("0.70") - score)
            return min(dist_to_weak, dist_to_hot) / Decimal("0.35")
```

### Task 3: Add state tracking to SectorScore
**File**: `src/market/models.py` (modify SectorScore)

Add fields:
```python
state_confidence = Column(Float)  # 0-1, distance from boundaries
consecutive_days = Column(Integer, default=0)  # Days in current state
```

### Task 4: Create query interface
**File**: `src/market/state_machine.py` (append)

```python
class SectorStateQueries:
    """Query sector states."""
    
    @staticmethod
    async def get_current_states() -> Dict[str, SectorState]:
        """Get current state for all sectors."""
    
    @staticmethod
    async def get_sectors_by_state(state: SectorState) -> List[str]:
        """Get list of sectors in a given state."""
    
    @staticmethod
    async def get_state_history(sector_id: str, days: int = 30) -> List[Tuple[date, SectorState]]:
        """Get state history for a sector."""
    
    @staticmethod
    async def get_recent_transitions(days: int = 7) -> List[StateTransition]:
        """Get sectors that changed state recently."""
```

### Task 5: Create unit tests
**File**: `tests/test_state_machine.py`

Test cases:
- State determination (simple thresholds)
- Hysteresis transitions (weak→normal, normal→overheated, etc.)
- Confidence calculation
- Consecutive days tracking
- State history queries
- Recent transitions query

## Success Criteria
- [ ] SectorState enum with hysteresis logic
- [ ] StateTransitionService updates states correctly
- [ ] Consecutive days tracked properly
- [ ] Confidence scores calculated
- [ ] Query methods return correct data
- [ ] Unit tests pass

## Dependencies
- MARKET-01: Sector radar scores (completed)

## Notes
- Hysteresis prevents rapid state flipping
- Confidence score helps downstream layers assess reliability
- State history useful for backtesting
