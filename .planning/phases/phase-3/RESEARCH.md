# Phase 3 Research: Logic Layer

**Phase**: 3  
**Name**: Logic Layer  
**Goal**: LLM-driven logic identification and event scorecard rule engine  
**Research Date**: 2026-04-19

---

## Overview

Phase 3 implements the core "logic layer" that distinguishes this system: **logic truth is independent of price**. The LLM identifies logics and extracts events, but **does not score them** — scoring is done by a deterministic rule engine (event scorecard) to ensure interpretability and backtestability.

### Key Architectural Decisions

1. **Two-stage pipeline**: 
   - Stage 1: LLM identifies logic definitions (logic_id, direction, family, importance)
   - Stage 2: LLM extracts events from news and associates them to logic_ids
   
2. **Event scorecard**: Deterministic rules for scoring (加减分), natural decay, validity tracking

3. **Fingerprint deduplication**: SHA256-based event deduplication within 24-hour window

4. **Net thrust calculation**: Aggregates positive/negative events with anti-logic flagging

5. **LLM degradation**: Fallback to previous day's data with decay when service unavailable

---

## LOGIC-01: LLM Logic Identification Service

### Purpose
Identify and categorize investment logics from news/text input.

### Output Schema
```python
{
    "logic_id": "policy_5g_development_001",
    "logic_name": "5G 产业发展政策",
    "logic_family": "policy",  # technology/policy/earnings/m_a/supply_chain
    "direction": "positive",   # positive/negative
    "importance_level": "high", # high/medium/low
    "description": "...",
    "keywords": ["5G", "产业政策", "工信部"],
    "validity_days": 30
}
```

### Implementation Pattern
- Use structured JSON output from LLM
- Validate logic_family against allowed values
- Generate unique logic_id: `{family}_{sequence}`
- Store in `logics` table

### Key Considerations
- Logic family taxonomy must be consistent
- Importance level drives score multiplier (high=1.5, medium=1.0, low=0.5)
- Validity period determines event expiration

---

## LOGIC-02: LLM Event Extraction Service

### Purpose
Extract individual events from news articles and associate with existing logic_ids.

### Two-Stage Pipeline
```
Stage 1: Logic Identification (LOGIC-01)
  Input: News corpus
  Output: List of logic definitions

Stage 2: Event Extraction (LOGIC-02)
  Input: News article + logic definitions
  Output: Events with logic_id associations
```

### Output Schema
```python
{
    "event_id": "evt_20260419_001",
    "logic_id": "policy_5g_development_001",
    "event_date": "2026-04-19",
    "source": "财联社",
    "headline": "工信部发布 5G 产业发展指导意见",
    "content_hash": "sha256(...)",
    "strength_raw": 0.85,  # LLM-assessed raw strength
    "direction": "positive"  # Inherited from logic
}
```

### Key Considerations
- Event extraction prompt includes logic definitions as context
- LLM outputs raw strength (0.0-1.0), NOT final score
- Direction inherited from associated logic (not re-evaluated)
- Content hash for deduplication

---

## LOGIC-03: Event Scorecard Rule Engine

### Purpose
Apply deterministic scoring rules to events, replacing LLM subjective scoring.

### Scoring Rules

#### 1. Base Score (strength_adjusted)
```python
strength_adjusted = strength_raw × importance_multiplier

Where:
- importance_multiplier: high=1.5, medium=1.0, low=0.5
```

#### 2. Natural Decay
```python
decayed_strength = strength_adjusted × (1.0 - days_since_event / half_life)

Where:
- half_life: configurable (default 7 days)
- Minimum: 0.0 (no negative decay)
```

#### 3. Validity Period
```python
validity_start = event_date
validity_end = event_date + logic.validity_days
is_expired = current_date > validity_end
```

### Implementation Pattern
- Apply rules in order: base score → decay → validity
- Store both `strength_raw` and `strength_adjusted` in database
- Decay computed at query time (not stored)

---

## LOGIC-04: Event Fingerprint Validation

### Purpose
Detect and filter duplicate events within 24-hour window.

### Fingerprint Algorithm
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

### Deduplication Window
- Check for existing fingerprints within 24 hours
- If match found: mark as duplicate (`is_duplicate=True`)
- Duplicates excluded from net thrust calculation

### Implementation
```python
async def compute_fingerprint(self, event: EventModel) -> str:
    content = f"{event.logic_id}|{event.event_date}|{self._normalize(event.headline)}"
    return hashlib.sha256(content.encode()).hexdigest()

async def is_duplicate(self, fingerprint: str, window_hours: int = 24) -> bool:
    cutoff = datetime.now() - timedelta(hours=window_hours)
    result = await session.execute(
        select(EventModel).where(
            EventModel.fingerprint == fingerprint,
            EventModel.created_at >= cutoff
        )
    )
    return result.scalar() is not None
```

---

## LOGIC-05: Net Thrust Calculation

### Purpose
Aggregate positive/negative events per logic with anti-logic flagging.

### Calculation
```python
positive_strength = sum(e.strength_adjusted for e in positive_events)
negative_strength = sum(e.strength_adjusted for e in negative_events)
net_thrust = positive_strength - negative_strength
has_anti_logic = (positive_strength > 0 and negative_strength > 0)
```

### Output Schema (LogicScore)
```python
{
    "logic_id": "...",
    "snapshot_date": "2026-04-19",
    "raw_score": 2.5,          # sum of all event strengths
    "decayed_score": 1.7,      # |net_thrust| after decay
    "net_thrust": 1.7,         # positive - negative
    "has_anti_logic": True,    # both sides present
    "event_count": 5,
    "positive_event_count": 3,
    "negative_event_count": 2
}
```

### Anti-Logic Flag Significance
- `has_anti_logic=True` indicates conflicting signals
- Downstream layers may reduce position size for anti-logic logics
- Represents market disagreement on logic direction

---

## LOGIC-06: LLM Service Degradation Strategy

### Purpose
Handle LLM service outages gracefully with fallback to previous day's data.

### Service States
```python
class LLMServiceStatus(Enum):
    full = "full"       # All services operational
    degraded = "degraded"  # Partial functionality
    offline = "offline"    # Complete outage
```

### Fallback Logic
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

### Implementation Pattern
- Monitor LLM health with heartbeat checks
- Store `llm_service_status` and `fallback_applied` in LogicScore
- Log `fallback_reason` for debugging

---

## Database Schema Reference

### logics table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| logic_id | String(64) | Unique logic identifier |
| logic_name | String(256) | Logic name |
| logic_family | String(128) | Family (technology/policy/earnings/m_a/supply_chain) |
| direction | Enum | positive/negative |
| importance_level | Enum | high/medium/low |
| description | Text | Logic description |
| keywords | JSON | Keyword list |
| validity_days | Integer | Validity period in days |
| is_active | Boolean | Active flag |

### events table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| event_id | String(64) | Unique event identifier |
| logic_id | String(64) | FK to logics.logic_id |
| event_date | Date | Event date |
| source | String(50) | News source |
| headline | String(500) | Event headline |
| content_hash | String(64) | SHA256 of content |
| strength_raw | Numeric(5,4) | Raw strength (0-1) |
| strength_adjusted | Numeric(5,4) | Adjusted strength (importance × decay) |
| direction | Enum | positive/negative |
| validity_start | Date | Validity period start |
| validity_end | Date | Validity period end |
| is_expired | Boolean | Expiration flag |
| fingerprint | String(64) | Deduplication fingerprint |
| is_duplicate | Boolean | Duplicate flag |

### logic_scores table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| logic_id | String(64) | FK to logics.logic_id |
| snapshot_date | Date | Snapshot date |
| raw_score | Numeric(7,4) | Sum of event strengths |
| decayed_score | Numeric(7,4) | After decay |
| net_thrust | Numeric(7,4) | Positive - Negative |
| has_anti_logic | Boolean | Anti-logic flag |
| event_count | Integer | Total events |
| positive_event_count | Integer | Positive events |
| negative_event_count | Integer | Negative events |
| llm_service_status | Enum | full/degraded/offline |
| fallback_applied | Boolean | Fallback used |
| fallback_reason | String(200) | Fallback reason |

---

## Implementation Sequence

1. **LOGIC-01**: Logic identification service + database models
2. **LOGIC-02**: Event extraction service
3. **LOGIC-03**: Event scorecard rule engine
4. **LOGIC-04**: Fingerprint deduplication service
5. **LOGIC-05**: Net thrust calculation + daily snapshot job
6. **LOGIC-06**: LLM health monitor + degradation service

---

## Sources

- Project REQUIREMENTS.md (LOGIC-01 through LOGIC-06)
- Existing models in src/logic/models.py
- Existing services in src/logic/*.py (verified functional)
