---
plan_id: LOGIC-02
phase: 3
requirement: LOGIC-02
title: LLM Event Extraction Service
description: Implement two-stage event extraction pipeline associating events to logic_ids
type: feature
estimated_effort: 2h
---

# Plan: LOGIC-02 - LLM Event Extraction Service

## Goal
Implement LLM-based event extraction service that extracts events from news and associates them with existing logic definitions.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md
- Models: src/logic/models.py (EventModel)
- LLM client: src/llm/client.py
- Logic service: src/logic/llm_service.py (LOGIC-01 output)

## Two-Stage Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: Logic Identification (LOGIC-01)                    │
│ Input: News corpus / Text                                   │
│ Output: List of logic definitions (logic_id, direction...)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: Event Extraction (LOGIC-02)                        │
│ Input: News article + Logic definitions                     │
│ Output: Events with logic_id associations + strength_raw    │
└─────────────────────────────────────────────────────────────┘
```

## Tasks

### Task 1: Create event extraction prompt template
**File**: `src/logic/prompts.py` (append)

```python
EVENT_EXTRACTION_PROMPT = """
You are an event extraction specialist. Extract investment events from news articles.

Given:
1. A list of active investment logics with their definitions
2. A news article

Your task:
1. Determine if the news article relates to any existing logic
2. If yes, extract event details and associate with the appropriate logic_id
3. Assess the raw strength of the event (0.0 - 1.0)

Output format: JSON array of event objects.

Example:
[
  {{
    "event_id": "evt_20260419_001",
    "logic_id": "policy_5g_development_001",
    "event_date": "2026-04-19",
    "source": "财联社",
    "headline": "工信部发布 5G 产业发展指导意见",
    "strength_raw": 0.85,
    "content_summary": "工信部发布指导意见，提出 2027 年 5G 基站数达 300 万个"
  }}
]

If no events extracted, output empty array: []

Active Logics:
{logics_json}

News Article:
{news_text}
"""
```

### Task 2: Implement EventExtractionService
**File**: `src/logic/event_extractor.py` (create)

```python
class EventExtractionService:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def extract_events(
        self,
        news_text: str,
        active_logics: List[LogicModel],
        source: str = None
    ) -> List[EventDefinition]:
        """Extract events from news article."""
        # Prepare logics context
        logics_json = json.dumps([
            {
                "logic_id": l.logic_id,
                "logic_name": l.logic_name,
                "direction": l.direction.value,
                "description": l.description
            }
            for l in active_logics
        ], ensure_ascii=False)
        
        prompt = EVENT_EXTRACTION_PROMPT.format(
            logics_json=logics_json,
            news_text=news_text
        )
        
        response = await self.llm_client.generate_json(prompt)
        
        return [EventDefinition(**item) for item in response]
    
    async def save_event(self, event: EventDefinition) -> EventModel:
        """Save event to database."""
        async with async_session_maker() as session:
            # Check for existing event with same content_hash
            existing = await session.execute(
                select(EventModel).where(
                    EventModel.content_hash == event.content_hash
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"Event already exists: {event.content_hash}")
                return None
            
            model = EventModel(
                event_id=event.event_id,
                logic_id=event.logic_id,
                event_date=event.event_date,
                source=event.source or source,
                headline=event.headline,
                content_hash=event.content_hash,
                strength_raw=event.strength_raw,
                direction=self._get_direction(event.logic_id, active_logics),
                is_expired=False
            )
            session.add(model)
            await session.commit()
            return model
    
    def _get_direction(self, logic_id: str, logics: List[LogicModel]) -> str:
        """Inherit direction from associated logic."""
        for logic in logics:
            if logic.logic_id == logic_id:
                return logic.direction.value
        return "positive"  # Default
```

### Task 3: Add content hash computation
**File**: `src/logic/event_extractor.py` (append)

```python
def compute_content_hash(headline: str, content: str, source: str) -> str:
    """Compute SHA256 hash for deduplication."""
    content_str = f"{headline}|{content}|{source}"
    return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
```

### Task 4: Implement batch processing
**File**: `src/logic/event_extractor.py` (append)

```python
async def process_news_batch(
    self,
    news_articles: List[NewsArticle],
    batch_size: int = 10
) -> List[EventModel]:
    """Process batch of news articles."""
    all_events = []
    
    # Get active logics once
    async with async_session_maker() as session:
        result = await session.execute(
            select(LogicModel).where(LogicModel.is_active == True)
        )
        active_logics = result.scalars().all()
    
    for i in range(0, len(news_articles), batch_size):
        batch = news_articles[i:i + batch_size]
        tasks = [
            self.extract_and_save(article, active_logics)
            for article in batch
        ]
        batch_events = await asyncio.gather(*tasks)
        all_events.extend([e for e in batch_events if e])
    
    return all_events
```

### Task 5: Create unit tests
**File**: `tests/test_event_extraction.py` (create)

Test cases:
- Test event extraction with matching logic
- Test event extraction with no matching logic
- Test strength_raw assessment
- Test content hash computation
- Test duplicate detection
- Test direction inheritance

## Success Criteria
- [ ] EventExtractionService extracts events from news
- [ ] Events correctly associated with logic_ids
- [ ] Direction inherited from parent logic
- [ ] Content hash computed for deduplication
- [ ] Batch processing works efficiently
- [ ] Unit tests pass

## Dependencies
- LOGIC-01: Logic identification (completed)
- INFRA-01: Database models (completed)

## Notes
- Event extraction runs daily on new news articles
- LLM only extracts raw strength, NOT final score
- Final scoring done by EventScorecard (LOGIC-03)
