---
plan_id: LOGIC-04
phase: 3
requirement: LOGIC-04
title: Event Fingerprint Validation
description: Implement SHA256-based event deduplication within 24-hour window
type: feature
estimated_effort: 1h
---

# Plan: LOGIC-04 - Event Fingerprint Validation

## Goal
Implement fingerprint-based deduplication to detect and filter duplicate events within a 24-hour window.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md (LOGIC-04 section)
- Models: src/logic/models.py (EventModel.fingerprint, EventModel.is_duplicate)
- Event source: src/logic/event_extractor.py (LOGIC-02 output)

## Fingerprint Algorithm

```python
fingerprint = SHA256(
    logic_id + "|" + 
    event_date.isoformat() + "|" + 
    normalize(headline) + "|" + 
    normalize(source)
)

Where normalize(s):
    - Lowercase
    - Remove punctuation
    - Remove whitespace
```

## Tasks

### Task 1: Implement EventFingerprintService
**File**: `src/logic/fingerprint.py` (create)

```python
import hashlib
import re
from datetime import datetime, timedelta

class EventFingerprintService:
    """Compute and validate event fingerprints for deduplication."""
    
    def _normalize(self, text: str) -> str:
        """Normalize text for fingerprint computation."""
        if not text:
            return ""
        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace
        text = ''.join(text.split())
        return text
    
    def compute_fingerprint(
        self,
        logic_id: str,
        event_date: date,
        headline: str,
        source: str
    ) -> str:
        """Compute SHA256 fingerprint for event."""
        normalized_headline = self._normalize(headline)
        normalized_source = self._normalize(source)
        
        content = f"{logic_id}|{event_date.isoformat()}|{normalized_headline}|{normalized_source}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def is_duplicate(
        self,
        fingerprint: str,
        window_hours: int = 24
    ) -> bool:
        """Check if fingerprint exists within time window."""
        cutoff = datetime.now() - timedelta(hours=window_hours)
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(EventModel).where(
                    EventModel.fingerprint == fingerprint,
                    EventModel.created_at >= cutoff
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def validate_and_mark(
        self,
        event: EventModel
    ) -> bool:
        """Compute fingerprint and mark event as duplicate if needed."""
        # Compute fingerprint
        fingerprint = self.compute_fingerprint(
            event.logic_id,
            event.event_date,
            event.headline,
            event.source
        )
        event.fingerprint = fingerprint
        
        # Check for duplicates
        is_dup = await self.is_duplicate(fingerprint)
        event.is_duplicate = is_dup
        
        return is_dup
```

### Task 2: Integrate with event extraction pipeline
**File**: `src/logic/event_extractor.py` (modify)

Add fingerprint validation to `save_event` method:

```python
async def save_event(self, event: EventDefinition) -> EventModel:
    """Save event to database with fingerprint validation."""
    async with async_session_maker() as session:
        model = EventModel(
            event_id=event.event_id,
            logic_id=event.logic_id,
            event_date=event.event_date,
            source=event.source,
            headline=event.headline,
            content_hash=event.content_hash,
            strength_raw=event.strength_raw,
            direction=self._get_direction(event.logic_id, active_logics),
            is_expired=False
        )
        
        # Compute and check fingerprint
        fingerprint_service = EventFingerprintService()
        is_duplicate = await fingerprint_service.validate_and_mark(model)
        
        if is_duplicate:
            logger.info(f"Duplicate event detected: {event.headline}")
            # Still save but mark as duplicate
            model.is_duplicate = True
        
        session.add(model)
        await session.commit()
        return model
```

### Task 3: Add deduplication query helper
**File**: `src/logic/fingerprint.py` (append)

```python
class FingerprintQueries:
    """Query helpers for fingerprint-based operations."""
    
    @staticmethod
    async def get_unique_events(
        logic_id: str = None,
        as_of_date: date = None
    ) -> List[EventModel]:
        """Get only non-duplicate events."""
        async with async_session_maker() as session:
            query = select(EventModel).where(
                EventModel.is_duplicate == False
            )
            
            if logic_id:
                query = query.where(EventModel.logic_id == logic_id)
            
            result = await session.execute(query.order_by(EventModel.event_date.desc()))
            return result.scalars().all()
    
    @staticmethod
    async def count_duplicates(
        start_date: date,
        end_date: date
    ) -> int:
        """Count duplicate events in date range."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count()).where(
                    EventModel.is_duplicate == True,
                    EventModel.event_date >= start_date,
                    EventModel.event_date <= end_date
                )
            )
            return result.scalar()
```

### Task 4: Create unit tests
**File**: `tests/test_fingerprint.py`

Test cases:
- Test fingerprint computation (deterministic)
- Test normalization (case, punctuation, whitespace)
- Test duplicate detection within 24h window
- Test no duplicate detection outside window
- Test same headline different logic_id
- Test integration with event extraction

## Success Criteria
- [ ] Fingerprint computation is deterministic
- [ ] Normalization handles Chinese text correctly
- [ ] Duplicates detected within 24-hour window
- [ ] Non-duplicates pass through correctly
- [ ] Integration with event extraction works
- [ ] Unit tests pass

## Dependencies
- LOGIC-02: Event extraction (completed)
- INFRA-01: Database models (completed)

## Notes
- 24-hour window is configurable
- Fingerprint stored in database for auditing
- Duplicate events still saved (marked) for audit trail
