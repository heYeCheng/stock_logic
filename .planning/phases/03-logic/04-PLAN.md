# Plan: LOGIC-04 — Event Fingerprint Validation

**Phase:** 3 (Logic Layer)  
**Requirement:** LOGIC-04  
**Created:** 2026-04-19  
**Status:** Ready for execution

---

## Goal

Implement event fingerprint validation system that:
1. Generates unique fingerprints for events
2. Detects duplicate events within 24-hour window
3. Handles cross-source duplicates (same event from different sources)
4. Filters duplicates before scorecard processing

---

## Scope

**In scope:**
- Fingerprint generation algorithm (SHA256 hash)
- Duplicate detection query
- 24-hour deduplication window
- Cross-source duplicate handling
- Database unique constraint enforcement

**Out of scope:**
- Logic identification (LOGIC-01)
- Event extraction (LOGIC-02)
- Scoring rules (LOGIC-03)
- Net thrust calculation (LOGIC-05)

---

## Implementation Plan

### 1. Fingerprint Service (`src/logic/fingerprint.py`)

```python
import hashlib
from datetime import datetime, timedelta
from typing import Optional

class EventFingerprintService:
    """Generate and validate event fingerprints for deduplication"""
    
    DEDUP_WINDOW_HOURS = 24  # Duplicate detection window
    
    def generate_fingerprint(self, event_data: dict) -> str:
        """
        Generate unique fingerprint for event
        
        Fingerprint components:
        1. source: News source identifier
        2. event_date: Date when event occurred
        3. logic_id: Associated logic
        4. headline_prefix: First 50 chars of headline
        
        Returns:
            64-character hex string (SHA256)
        """
        source = event_data.get("source", "unknown")
        event_date = event_data.get("event_date", "")
        logic_id = event_data.get("logic_id", "")
        headline = event_data.get("headline", "")
        
        # Normalize headline (remove whitespace variations)
        headline_normalized = " ".join(headline.split())
        headline_prefix = headline_normalized[:50]
        
        # Create canonical string
        canonical = f"{source}|{event_date}|{logic_id}|{headline_prefix}"
        
        # Generate SHA256 hash
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        
        return fingerprint
    
    async def is_duplicate(
        self, 
        fingerprint: str, 
        event_date: datetime
    ) -> bool:
        """
        Check if event with same fingerprint exists within dedup window
        
        Args:
            fingerprint: Pre-computed fingerprint
            event_date: Date of the event
        
        Returns:
            True if duplicate found within 24-hour window
        """
        async with async_session_maker() as session:
            # Query for existing event with same fingerprint
            # within 24-hour window
            window_start = event_date - timedelta(hours=self.DEDUP_WINDOW_HOURS)
            window_end = event_date + timedelta(hours=self.DEDUP_WINDOW_HOURS)
            
            result = await session.execute(
                select(Event).where(
                    Event.fingerprint == fingerprint,
                    Event.event_date >= window_start,
                    Event.event_date <= window_end
                )
            )
            
            existing = result.scalar_one_or_none()
            return existing is not None
    
    async def find_cross_source_duplicate(
        self,
        logic_id: str,
        event_date: datetime,
        headline: str
    ) -> Optional[Event]:
        """
        Find duplicate from different source
        
        Some events are reported by multiple sources.
        We want to keep the one with highest strength.
        
        Returns:
            Existing event if found, None otherwise
        """
        async with async_session_maker() as session:
            # Fuzzy match: same logic_id, same date, similar headline
            # Use headline prefix for matching
            headline_prefix = headline[:50]
            
            result = await session.execute(
                select(Event).where(
                    Event.logic_id == logic_id,
                    Event.event_date == event_date.date(),
                    Event.headline.like(f"{headline_prefix}%")
                )
            )
            
            existing = result.scalar_one_or_none()
            return existing
    
    def should_replace(
        self, 
        existing: Event, 
        new_strength: Decimal
    ) -> bool:
        """
        Determine if new event should replace existing
        
        Keep the event with higher strength_raw
        """
        return new_strength > existing.strength_raw
```

### 2. Event Service with Deduplication (`src/logic/event_service.py`)

```python
class EventService:
    """Event persistence with deduplication"""
    
    def __init__(self):
        self.fingerprint_service = EventFingerprintService()
    
    async def save_event_with_dedup(
        self, 
        event: Event,
        skip_duplicates: bool = True
    ) -> tuple[Event, bool]:
        """
        Save event with duplicate check
        
        Args:
            event: Event to save
            skip_duplicates: If True, skip on duplicate. If False, keep highest strength.
        
        Returns:
            (event, is_new) tuple
            - is_new = True if new event inserted
            - is_new = False if duplicate found
        """
        # Generate fingerprint
        fingerprint = self.fingerprint_service.generate_fingerprint({
            "source": event.source,
            "event_date": event.event_date,
            "logic_id": event.logic_id,
            "headline": event.headline
        })
        
        event.fingerprint = fingerprint
        
        # Check for duplicate
        is_dup = await self.fingerprint_service.is_duplicate(
            fingerprint, 
            event.event_date
        )
        
        async with async_session_maker() as session:
            if is_dup:
                if skip_duplicates:
                    logger.debug(f"Duplicate event detected, skipping: {fingerprint}")
                    return event, False
                
                # Check cross-source duplicate (keep higher strength)
                existing = await self.fingerprint_service.find_cross_source_duplicate(
                    event.logic_id,
                    event.event_date,
                    event.headline
                )
                
                if existing and self.fingerprint_service.should_replace(
                    existing, event.strength_raw
                ):
                    logger.info(f"Replacing lower-strength event: {existing.event_id}")
                    # Update existing with new strength
                    existing.strength_raw = event.strength_raw
                    existing.source = event.source
                    await session.commit()
                    return existing, False
                else:
                    logger.debug(f"Duplicate event not better, skipping")
                    return event, False
            
            # Insert new event
            session.add(event)
            await session.commit()
            logger.info(f"New event saved: {event.event_id}")
            return event, True
```

### 3. Database Model Update (`src/logic/models.py`)

```python
class Event(Base):
    __tablename__ = "events"
    
    # ... existing fields ...
    
    # Deduplication
    fingerprint = Column(String(64), unique=True, index=True)
    is_duplicate = Column(Boolean, default=False)
    replaced_by = Column(String(64), ForeignKey("events.event_id"), nullable=True)
    
    __table_args__ = (
        # Unique constraint for additional safety
        UniqueConstraint('source', 'event_date', 'logic_id', 'headline', name='uq_event_source_date_logic_headline'),
    )
```

### 4. Integration Test

```python
async def test_fingerprint_deduplication():
    """Test fingerprint-based deduplication"""
    
    fingerprint_service = EventFingerprintService()
    event_service = EventService()
    
    # Create first event
    event1 = Event(
        event_id="event_001",
        logic_id="policy_5g_001",
        event_date=datetime.now(),
        source="sina",
        headline="工信部发布 5G 发展指导意见",
        strength_raw=Decimal("0.8")
    )
    
    # Save first event
    saved1, is_new1 = await event_service.save_event_with_dedup(event1)
    assert is_new1 == True
    
    # Create duplicate event (same content, same source)
    event2 = Event(
        event_id="event_002",
        logic_id="policy_5g_001",
        event_date=datetime.now(),
        source="sina",
        headline="工信部发布 5G 发展指导意见",
        strength_raw=Decimal("0.8")
    )
    
    # Try to save duplicate
    saved2, is_new2 = await event_service.save_event_with_dedup(event2)
    assert is_new2 == False  # Should be detected as duplicate
    
    # Create cross-source event (different source, same content)
    event3 = Event(
        event_id="event_003",
        logic_id="policy_5g_001",
        event_date=datetime.now(),
        source="eastmoney",
        headline="工信部发布 5G 发展指导意见",
        strength_raw=Decimal("0.9")  # Higher strength
    )
    
    # Save cross-source event (should replace if higher strength)
    saved3, is_new3 = await event_service.save_event_with_dedup(
        event3, 
        skip_duplicates=False
    )
    # Should replace existing with higher strength version
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/logic/fingerprint.py` | Create | Fingerprint generation and validation |
| `src/logic/event_service.py` | Create | Event service with deduplication |
| `src/logic/models.py` | Modify | Add fingerprint field to Event |
| `tests/logic/test_fingerprint.py` | Create | Unit tests for fingerprint |
| `alembic/versions/xxx_add_fingerprint.py` | Create | Migration for fingerprint column |

---

## Dependencies

- LOGIC-02: Event extraction (provides events)
- Phase 1: Database layer with unique constraints

---

## Success Criteria

1. ✅ Fingerprint generated deterministically from event fields
2. ✅ Duplicate events detected within 24-hour window
3. ✅ Cross-source duplicates handled (keep highest strength)
4. ✅ Database unique constraint on fingerprint
5. ✅ Duplicate events marked, not deleted (audit trail)
6. ✅ Integration test passes with duplicate scenarios

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fingerprint collision | False duplicate detection | SHA256 has negligible collision rate |
| 24-hour window too narrow | Missed duplicates | Monitor, adjust window if needed |
| Headline normalization | False negatives | Test with real headline variations |
| Database constraint errors | Insert failures | Handle IntegrityError gracefully |

---

## Execution Notes

- Test with real news headline variations
- Monitor duplicate detection rate
- Log all fingerprint computations for debugging
- Consider headline stemming for better matching

---

*Plan created: 2026-04-19*
