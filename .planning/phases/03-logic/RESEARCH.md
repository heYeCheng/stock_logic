# Phase 3: Logic Layer - Research Summary

**Researched:** 2026-04-19  
**Domain:** LLM-Driven Event Extraction and Scorecard Rule Engine for A-Stock Trading  
**Confidence:** HIGH (established patterns in NLP finance + novel scorecard design)

---

## 1. Two-Stage Pipeline Architecture

### Overview

The Logic Layer uses a **two-stage pipeline** to separate logic identification from event extraction:

```
Stage 1: Logic Identification          Stage 2: Event Extraction
─────────────────────────             ─────────────────────────
News Text → LLM → Logic List          News Text + Logic Schema → LLM → Events
                                     
Output:                               Output:
- logic_id (unique identifier)        - event_id (fingerprint)
- logic_family (category)             - logic_id (foreign key)
- direction (positive/negative)       - event_date
- importance_level (H/M/L)            - strength_raw (LLM confidence)
- description                         - validity_start/end
```

### Why Two Stages?

| Benefit | Explanation |
|---------|-------------|
| **Consistency** | Logic schema defined once, events mapped to stable logic_ids |
| **Efficiency** | LLM doesn't rediscover logics for each news article |
| **Auditability** | Clear trace: event → logic → score contribution |
| **Backtesting** | Logic schema versioned, events re-extractable |

### Logic Schema Example

```json
{
  "logic_id": "tech_breakthrough_001",
  "logic_family": "technology",
  "direction": "positive",
  "importance_level": "high",
  "description": "技术突破类逻辑 - 适用于半导体、AI 等领域",
  "keywords": ["技术突破", "国产替代", "卡脖子", "自主研发"],
  "validity_days": 30
}
```

---

## 2. Event Scorecard Rule Engine

### Core Design

The scorecard applies **加减分 rules** to compute net thrust for each logic_id:

```python
class EventScorecard:
    def __init__(self, logic_id: str):
        self.logic_id = logic_id
        self.events: List[Event] = []
        self.current_score: float = 0.0
        self.decay_rate: float = 0.95  # 5% daily decay
    
    def add_event(self, event: Event) -> None:
        self.events.append(event)
        self.current_score += event.strength_adjusted
    
    def apply_decay(self, days: int) -> None:
        """Natural decay over time"""
        self.current_score *= (self.decay_rate ** days)
    
    def get_net_thrust(self) -> float:
        """Net thrust with anti-logic flagging"""
        positive = sum(e.strength for e in self.events if e.direction == 'positive')
        negative = sum(e.strength for e in self.events if e.direction == 'negative')
        
        net_thrust = positive - negative
        has_anti_logic = (positive > 0 and negative > 0)
        
        return net_thrust, has_anti_logic
```

### Scoring Rules

| Rule Type | Trigger | Score Adjustment |
|-----------|---------|------------------|
| **Fresh Event** | New event detected | +strength_raw × importance_multiplier |
| **Natural Decay** | Each day elapsed | × 0.95 (5% daily decay) |
| **Validity Expiry** | Days > validity_days | Score → 0 |
| **Duplicate Filter** | Fingerprint match | Rejected |
| **Anti-Logic Flag** | Both +/- events exist | Flagged for review |

### Importance Multipliers

| Level | Multiplier | Example |
|-------|------------|---------|
| **High** | 1.5 | 国家级政策、重大技术突破 |
| **Medium** | 1.0 | 行业级新闻、常规财报 |
| **Low** | 0.5 | 媒体报道、分析师点评 |

---

## 3. Event Fingerprint Validation

### Duplicate Detection Strategy

```python
def generate_fingerprint(event: Event) -> str:
    """Generate unique fingerprint for deduplication"""
    content = f"{event.source}:{event.event_date}:{event.logic_id}:{event.headline[:50]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def is_duplicate(new_event: Event, existing_events: List[Event]) -> bool:
    """Check if new event is duplicate"""
    new_fp = generate_fingerprint(new_event)
    for existing in existing_events:
        if generate_fingerprint(existing) == new_fp:
            return True
    return False
```

### Fingerprint Components

1. **Source**: News source identifier (e.g., "sina", "eastmoney")
2. **Event Date**: Date when event occurred
3. **Logic ID**: Associated logic identifier
4. **Headline Prefix**: First 50 chars of headline (captures variation)

### Deduplication Window

- **24-hour window**: Events with same fingerprint within 24h = duplicate
- **Cross-source**: Same event from different sources = keep highest strength

---

## 4. LLM Service Degradation Strategy

### Degradation Levels

| Level | Condition | Fallback |
|-------|-----------|----------|
| **Full** | LLM API available, rate limit OK | Normal processing |
| **Degraded** | LLM API slow/rate-limited | Queue events, batch process |
| **Offline** | LLM API unavailable | Use previous day's data + decay |

### Offline Mode Logic

```python
async def get_logic_scores_with_degradation(date: date) -> Dict[str, float]:
    try:
        # Try normal LLM processing
        return await llm_service.extract_and_score(date)
    except LLMServiceUnavailable:
        # Fallback: use yesterday's scores with decay
        yesterday = date - timedelta(days=1)
        prior_scores = await db.get_scores(yesterday)
        
        decayed = {k: v * 0.9 for k, v in prior_scores.items()}  # 10% daily decay
        logger.warning(f"LLM offline, using decayed prior scores: {decayed}")
        
        return decayed
```

### Decay Rate Rationale

- **10% daily decay**: Events lose relevance quickly in A-stock market
- **7-day half-life**: After 7 days, score ≈ 50% of original
- **30-day expiry**: Most events invalid after 30 days

---

## 5. LLM Prompt Design

### Stage 1: Logic Identification Prompt

```
你是一名 A 股市场分析师，负责识别新闻中的投资逻辑。

任务：从新闻文本中提取逻辑类别，输出 JSON 格式：

{
  "logics": [
    {
      "logic_id": "<category>_<type>_<sequence>",
      "logic_family": "<technology|policy|earnings|m&a|supply_chain>",
      "direction": "<positive|negative>",
      "importance_level": "<high|medium|low>",
      "description": "<简短描述>",
      "confidence": <0.0-1.0>
    }
  ]
}

逻辑家族定义：
- technology: 技术突破、国产替代、研发进展
- policy: 国家政策、行业监管、税收优惠
- earnings: 财报超预期、盈利预警
- m&a: 并购重组、股权激励
- supply_chain: 供应链变化、大客户订单

新闻文本：
{news_text}

输出（仅 JSON，无其他文字）：
```

### Stage 2: Event Extraction Prompt

```
你是一名 A 股事件提取专家。

给定逻辑 schema 和新闻文本，提取具体事件：

逻辑 schema:
{logic_schema_json}

新闻文本：
{news_text}

输出 JSON 格式：

{
  "events": [
    {
      "event_id": "<fingerprint>",
      "logic_id": "<匹配的 logic_id>",
      "event_date": "<YYYY-MM-DD>",
      "headline": "<事件标题>",
      "strength_raw": <0.0-1.0>,
      "validity_days": <有效期天数>,
      "keywords": ["<关键词 1>", "<关键词 2>"]
    }
  ]
}

强度评分标准：
- 0.8-1.0: 国家级政策、重大技术突破
- 0.5-0.7: 行业级新闻、重要财报
- 0.3-0.4: 媒体报道、分析师点评
- 0.1-0.2: 传闻、不确定性高的信息

输出（仅 JSON，无其他文字）：
```

---

## 6. Database Schema Design

### Events Table

```sql
CREATE TABLE events (
    id INT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64) UNIQUE NOT NULL,  -- Fingerprint
    logic_id VARCHAR(64) NOT NULL,
    
    -- Event metadata
    event_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50),  -- News source
    headline VARCHAR(500),
    
    -- Scoring
    strength_raw DECIMAL(3,2),      -- 0.0-1.0
    strength_adjusted DECIMAL(3,2), -- After importance multiplier
    direction ENUM('positive', 'negative'),
    
    -- Validity
    validity_start DATE,
    validity_end DATE,
    is_expired BOOLEAN DEFAULT FALSE,
    
    -- Deduplication
    fingerprint VARCHAR(64) UNIQUE,
    is_duplicate BOOLEAN DEFAULT FALSE,
    
    INDEX idx_logic_date (logic_id, event_date),
    INDEX idx_fingerprint (fingerprint)
);
```

### Logics Table

```sql
CREATE TABLE logics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    logic_id VARCHAR(64) UNIQUE NOT NULL,
    logic_family VARCHAR(50),
    direction ENUM('positive', 'negative'),
    importance_level ENUM('high', 'medium', 'low'),
    description TEXT,
    keywords JSON,
    validity_days INT DEFAULT 30,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_family (logic_family),
    INDEX idx_active (is_active)
);
```

### Logic Scores Table (Daily Snapshot)

```sql
CREATE TABLE logic_scores (
    id INT PRIMARY KEY AUTO_INCREMENT,
    logic_id VARCHAR(64) NOT NULL,
    snapshot_date DATE NOT NULL,
    
    -- Scores
    raw_score DECIMAL(5,2),         -- Sum of event strengths
    decayed_score DECIMAL(5,2),     -- After decay
    net_thrust DECIMAL(5,2),        -- Positive - Negative
    has_anti_logic BOOLEAN,         -- Both +/- events exist
    
    -- Metadata
    event_count INT,
    llm_service_status ENUM('full', 'degraded', 'offline'),
    
    UNIQUE KEY unique_logic_date (logic_id, snapshot_date),
    INDEX idx_date (snapshot_date)
);
```

---

## 7. Implementation Considerations

### LLM Rate Limiting

| Provider | Rate Limit | Mitigation |
|----------|------------|------------|
| OpenAI GPT-4 | 10K tokens/min | Batch events, queue during peak |
| Anthropic Claude | 50K tokens/min | Higher throughput, prefer for batch |
| Local LLM | GPU memory | Quantized models, CPU fallback |

### Cost Optimization

- **Batch processing**: Group events by logic_family, single LLM call
- **Caching**: Cache logic schema, only re-extract events
- **Tiered processing**: High-importance events → GPT-4, low → cheaper model

### Latency Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Logic identification | <2s per article | Stage 1, cached schema |
| Event extraction | <5s per batch | Stage 2, batch of 10-20 articles |
| Scorecard update | <100ms | In-memory computation |
| Net thrust query | <50ms | Database index on logic_id + date |

---

## 8. Competitive Intelligence

### Industry Patterns

1. **Bloomberg Terminal**: Uses NLP for news sentiment, but proprietary models
2. **Wind/Choice**: Chinese financial data terminals with basic sentiment scoring
3. **Quantitative funds**: Custom LLM pipelines, rarely open-sourced

### Novel Aspects of This Design

| Feature | Industry Standard | This Design |
|---------|-------------------|-------------|
| Logic Schema | Implicit, model-dependent | Explicit, versioned, auditable |
| Two-Stage Pipeline | Single-pass scoring | Separation of logic/events |
| Scorecard Decay | Fixed window (e.g., 7 days) | Continuous exponential decay |
| Anti-Logic Flagging | Net sentiment only | Explicit flag for conflicting signals |

---

## 9. Recommendations for Phase 3

### MVP Scope (Must Have)

1. **LLM Logic Identification Service**
   - Stage 1 prompt for logic schema extraction
   - Logic persistence to `logics` table
   - Logic family taxonomy (5-10 categories)

2. **LLM Event Extraction Service**
   - Stage 2 prompt for event extraction
   - Event persistence to `events` table
   - Fingerprint generation + deduplication

3. **Event Scorecard Rule Engine**
   -加减分 rules implementation
   - Natural decay (0.95 daily)
   - Validity period tracking

4. **Net Thrust Calculation**
   - Positive - Negative aggregation
   - Anti-logic flagging
   - Daily snapshot to `logic_scores` table

5. **LLM Degradation Strategy**
   - Graceful fallback to prior day + decay
   - Logging for monitoring

### Deferred to Phase 4+

- Logic schema versioning and migration
- Multi-model LLM routing (cost optimization)
- Real-time event streaming (Phase 3 = batch only)
- Backtesting framework for decay rate optimization

---

## 10. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM hallucination | False events extracted | Confidence threshold, human review for low-confidence |
| Duplicate events | Score inflation | Fingerprint validation, 24h dedup window |
| Decay rate too aggressive | Events lose impact too fast | Configurable decay, backtest optimization |
| Anti-logic confusion | Conflicting signals cancel | Flag for review, don't auto-cancel |
| LLM API downtime | Pipeline stalls | Degradation to prior + decay, never crash |

---

## Sources

- LLM prompt engineering for finance: Anthropic Claude documentation
- Event extraction patterns: Academic NLP finance papers (FinBERT, FinNLP)
- Scorecard design: Credit scoring systems, FICO methodology
- Deduplication strategies: News aggregation systems (Google News, SmartNews)
- Decay modeling: Epidemiological SIR models adapted for information half-life

---

*Research completed: 2026-04-19*
