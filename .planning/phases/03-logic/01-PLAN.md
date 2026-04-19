# Plan: LOGIC-01 — LLM Logic Identification Service

**Phase:** 3 (Logic Layer)  
**Requirement:** LOGIC-01  
**Created:** 2026-04-19  
**Status:** Ready for execution

---

## Goal

Implement LLM service that identifies and categorizes investment logics from news text with structured output:
- `logic_id`: Unique identifier (e.g., `tech_breakthrough_001`)
- `direction`: Positive or negative
- `logic_family`: Category (technology, policy, earnings, m_a, supply_chain)
- `importance_level`: High, medium, or low
- `description`: Brief description in Chinese
- `confidence`: 0.0-1.0 confidence score

---

## Scope

**In scope:**
- LLM prompt design for logic identification
- JSON parsing and validation
- Logic persistence to database
- Deduplication of logic schemas (same logic from multiple articles)
- LiteLLM integration with error handling

**Out of scope:**
- Event extraction (LOGIC-02)
- Scoring rules (LOGIC-03)
- Fingerprint validation (LOGIC-04)

---

## Implementation Plan

### 1. Database Model (`src/logic/models.py`)

```python
class Logic(Base):
    __tablename__ = "logics"
    
    id = Column(Integer, primary_key=True)
    logic_id = Column(String(64), unique=True, nullable=False, index=True)
    logic_family = Column(String(50), nullable=False, index=True)
    direction = Column(Enum(LogicDirection), nullable=False)  # positive/negative
    importance_level = Column(Enum(ImportanceLevel), nullable=False)  # high/medium/low
    description = Column(Text, nullable=False)
    keywords = Column(JSON, nullable=True)  # Extracted keywords
    validity_days = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    events = relationship("Event", back_populates="logic", cascade="all, delete-orphan")
```

### 2. LLM Service (`src/logic/llm_service.py`)

```python
class LogicIdentificationService:
    """Stage 1: Identify logics from news text"""
    
    SYSTEM_PROMPT = """你是一名 A 股市场分析师，负责识别新闻中的投资逻辑。

任务：从新闻文本中提取逻辑类别，输出 JSON 格式：

{
  "logics": [
    {
      "logic_id": "<category>_<type>_<sequence>",
      "logic_family": "<technology|policy|earnings|m_a|supply_chain>",
      "direction": "<positive|negative>",
      "importance_level": "<high|medium|low>",
      "description": "<简短描述，20-50 字>",
      "keywords": ["<关键词 1>", "<关键词 2>"],
      "confidence": <0.0-1.0>
    }
  ]
}

逻辑家族定义：
- technology: 技术突破、国产替代、研发进展、专利获批
- policy: 国家政策、行业监管、税收优惠、补贴政策
- earnings: 财报超预期、盈利预警、分红回购、业绩大增
- m_a: 并购重组、股权激励、定增、股份回购
- supply_chain: 供应链变化、大客户订单、原材料价格、产能扩张

强度评分标准：
- high: 国家级政策、重大技术突破、业绩翻倍
- medium: 行业级新闻、常规财报、一般订单
- low: 媒体报道、分析师点评、市场传闻

输出（仅 JSON，无其他文字）："""

    async def identify_logics(self, news_text: str, source: str = None) -> List[Logic]:
        """Identify logics from news text"""
        # Call LLM
        response = await self._call_llm(news_text)
        
        # Parse and validate
        logics = self._parse_response(response)
        
        # Deduplicate and persist
        persisted = await self._save_logics(logics)
        
        return persisted
```

### 3. Deduplication Logic

```python
async def _save_logics(self, logics: List[Logic]) -> List[Logic]:
    """Save logics, skipping duplicates"""
    persisted = []
    
    async with async_session_maker() as session:
        for logic in logics:
            # Check if logic_id exists
            existing = await session.execute(
                select(Logic).where(Logic.logic_id == logic.logic_id)
            )
            existing = existing.scalar_one_or_none()
            
            if existing:
                # Update existing logic (new keywords, etc.)
                self._merge_logic(existing, logic)
                persisted.append(existing)
            else:
                # Insert new logic
                session.add(logic)
                persisted.append(logic)
        
        await session.commit()
    
    return persisted
```

### 4. Integration Test

```python
async def test_logic_identification():
    """Test with sample news text"""
    sample_news = """
    工信部发布《关于推动 5G 应用发展的指导意见》，提出到 2025 年，
    建成全球规模最大的 5G 网络，5G 用户普及率达到 50% 以上。
    对 5G 芯片、基站设备、终端模组等给予税收优惠和研发补贴。
    """
    
    service = LogicIdentificationService()
    logics = await service.identify_logics(sample_news)
    
    assert len(logics) > 0
    assert logics[0].logic_family == "policy"
    assert logics[0].direction == "positive"
    assert logics[0].importance_level == "high"
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/logic/__init__.py` | Create | Module initialization |
| `src/logic/models.py` | Create | ORM models for Logic, Event, LogicScore |
| `src/logic/llm_service.py` | Create | LLM prompt, parsing, deduplication |
| `src/logic/service.py` | Create | Orchestrator for logic identification |
| `tests/logic/test_llm_service.py` | Create | Unit tests for logic ID |
| `alembic/versions/xxx_logic_tables.py` | Create | Migration for logics table |

---

## Dependencies

- Phase 1: Database layer, LiteLLM integration
- Phase 2: None (Logic Layer is independent)
- External: LLM API (Claude or GPT-4)

---

## Success Criteria

1. ✅ `logics` table created with proper schema
2. ✅ LLM prompt returns valid JSON with all required fields
3. ✅ Duplicate logics detected and merged (same logic_id)
4. ✅ Logic families correctly classified (technology, policy, earnings, m_a, supply_chain)
5. ✅ Direction and importance_level correctly extracted
6. ✅ Confidence scores validated (0.0-1.0 range)
7. ✅ Integration test passes with sample news text

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM returns invalid JSON | Parsing fails | Retry with validation prompt, fallback to regex extraction |
| Logic family misclassification | Downstream scoring errors | Include clear definitions in prompt, validate against enum |
| Duplicate logics created | Data pollution | Unique constraint on logic_id, merge on conflict |
| LLM rate limiting | Slow processing | Batch news articles, implement exponential backoff |

---

## Execution Notes

- Run migration before testing: `alembic upgrade head`
- Test with real news text from Chinese financial sources
- Log all LLM calls for debugging
- Monitor confidence scores; if consistently low, adjust prompt

---

*Plan created: 2026-04-19*
