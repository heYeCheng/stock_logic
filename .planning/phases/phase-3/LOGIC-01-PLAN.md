---
plan_id: LOGIC-01
phase: 3
requirement: LOGIC-01
title: LLM Logic Identification Service
description: Implement LLM-based logic identification with structured JSON output
type: feature
estimated_effort: 2h
---

# Plan: LOGIC-01 - LLM Logic Identification Service

## Goal
Implement service that identifies and categorizes investment logics from news/text input with structured JSON output.

## Context
- Research: .planning/phases/phase-3/RESEARCH.md
- Models: src/logic/models.py (LogicModel, LogicDirection, ImportanceLevel, LogicFamily)
- LLM client: src/llm/client.py (LiteLLM integration)

## Tasks

### Task 1: Define logic family taxonomy
**File**: `src/logic/types.py` (create)

Create enum for logic families:
```python
class LogicFamily(str, Enum):
    technology = "technology"
    policy = "policy"
    earnings = "earnings"
    m_a = "m_a"
    supply_chain = "supply_chain"
    industry_trend = "industry_trend"
    product_cycle = "product_cycle"
```

### Task 2: Create logic identification prompt template
**File**: `src/logic/prompts.py` (create)

Create prompt template for logic identification:
```python
LOGIC_IDENTIFICATION_PROMPT = """
You are an investment logic analyst. Identify investment logics from the input text.

For each logic identified, output:
1. logic_id: Unique identifier (format: {family}_{short_name}_{sequence})
2. logic_name: Chinese name for the logic
3. logic_family: One of: technology, policy, earnings, m_a, supply_chain, industry_trend, product_cycle
4. direction: positive or negative
5. importance_level: high, medium, or low
6. description: 1-2 sentence description in Chinese
7. keywords: List of 5-8 relevant keywords
8. validity_days: Number of days this logic remains relevant (7-90)

Output format: JSON array of logic objects.

Example:
[
  {{
    "logic_id": "policy_5g_development_001",
    "logic_name": "5G 产业发展政策",
    "logic_family": "policy",
    "direction": "positive",
    "importance_level": "high",
    "description": "工信部发布 5G 产业发展指导意见，推动产业链升级",
    "keywords": ["5G", "产业政策", "工信部", "产业链", "升级"],
    "validity_days": 30
  }}
]

Input text:
{text}
"""
```

### Task 3: Implement LogicIdentificationService
**File**: `src/logic/llm_service.py` (create)

```python
class LogicIdentificationService:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def identify_logics(self, text: str) -> List[LogicDefinition]:
        """Identify logics from input text."""
        prompt = LOGIC_IDENTIFICATION_PROMPT.format(text=text)
        response = await self.llm_client.generate_json(prompt)
        return [LogicDefinition(**item) for item in response]
    
    async def register_logic(self, logic: LogicDefinition) -> LogicModel:
        """Register logic in database."""
        async with async_session_maker() as session:
            model = LogicModel(
                logic_id=logic.logic_id,
                logic_name=logic.logic_name,
                logic_family=logic.logic_family.value,
                direction=LogicDirection(logic.direction),
                importance_level=ImportanceLevel(logic.importance_level),
                description=logic.description,
                keywords=logic.keywords,
                validity_days=logic.validity_days,
                is_active=True
            )
            session.add(model)
            await session.commit()
            return model
```

### Task 4: Add validation logic
**File**: `src/logic/validators.py` (create)

```python
def validate_logic_id(logic_id: str) -> bool:
    """Validate logic_id format: {family}_{name}_{sequence}"""
    pattern = r'^[a-z]+_[a-z0-9]+_\d+$'
    return bool(re.match(pattern, logic_id))

def validate_logic_family(family: str) -> bool:
    """Validate logic family is in allowed taxonomy."""
    return family in [f.value for f in LogicFamily]

def validate_importance_level(level: str) -> bool:
    """Validate importance level."""
    return level in ['high', 'medium', 'low']
```

### Task 5: Create unit tests
**File**: `tests/test_logic_identification.py` (create)

Test cases:
- Test prompt formatting
- Test JSON parsing
- Test logic_id validation
- Test database registration
- Test duplicate logic detection

## Success Criteria
- [ ] LogicIdentificationService can parse news text and extract logics
- [ ] Output JSON matches expected schema
- [ ] Logic families validated against taxonomy
- [ ] Logics persisted to database correctly
- [ ] Unit tests pass

## Dependencies
- INFRA-01: Database models (completed)
- INFRA-04: LLM client (completed)

## Notes
- Logic identification is one-time setup per logic
- Re-run identification only when new logic family emerges
- Consider caching identified logics to reduce LLM calls
