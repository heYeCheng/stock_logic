---
plan_id: STOCK-03
phase: 4
requirement: STOCK-03
title: Keyword Auto-Generation
description: LLM generates 5-8 keywords for new sectors automatically
type: feature
estimated_effort: 1h
---

# Plan: STOCK-03 - Keyword Auto-Generation

## Goal
Implement LLM-based keyword generation that creates 5-8 keywords for new sectors automatically.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-03 section)
- Dependencies: Phase 3 (LLM client), STOCK-01 (sector mappings)

## Implementation Pattern

```python
async def generate_sector_keywords(sector_name: str, sector_stocks: List[str]) -> List[str]:
    """
    Use LLM to generate 5-8 keywords for a sector.
    
    Args:
        sector_name: e.g., "5G 概念"
        sector_stocks: List of stock names in sector
    
    Returns:
        List of 5-8 keywords
    """
    prompt = f"""
    为板块"{sector_name}"生成 5-8 个关键词。
    
    板块成分股：{', '.join(sector_stocks[:10])}
    
    关键词应该：
    1. 能准确描述板块特征
    2. 用于匹配相关新闻和逻辑
    3. 避免过于宽泛（如"科技"）或过于狭窄
    
    输出 JSON 格式：
    {{
        "keywords": ["关键词 1", "关键词 2", ...]
    }}
    """
    
    response = await llm_client.generate(prompt)
    return parse_keywords(response)
```

## Tasks

### Task 1: Create KeywordGenerator service
**File**: `src/market/keyword_generator.py` (create)

```python
import json
from typing import List, Optional
from src.llm.client import get_llm_client

class KeywordGenerator:
    """Generate keywords for sectors using LLM."""
    
    SYSTEM_PROMPT = """你是一个专业的 A 股市场分析师，擅长识别板块特征和关键词。

你的任务是为给定的板块生成 5-8 个关键词，这些关键词将用于：
1. 匹配相关新闻和事件
2. 与投资逻辑进行关联
3. 捕捉板块的核心特征

关键词应该：
- 具体且有区分度（避免"科技"、"消费"等过于宽泛的词）
- 能准确反映板块特征
- 适合用于新闻检索和匹配"""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.llm_client = get_llm_client()
    
    async def generate_keywords(
        self,
        sector_name: str,
        sector_stocks: List[str],
        sector_description: Optional[str] = None
    ) -> List[str]:
        """
        Generate keywords for a sector.
        
        Args:
            sector_name: Sector name (e.g., "5G 概念")
            sector_stocks: List of constituent stock names
            sector_description: Optional description
        
        Returns:
            List of 5-8 keywords
        """
        prompt = self._build_prompt(
            sector_name, sector_stocks, sector_description
        )
        
        response = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            model=self.model
        )
        
        return self._parse_keywords(response)
    
    def _build_prompt(
        self,
        sector_name: str,
        sector_stocks: List[str],
        description: Optional[str]
    ) -> str:
        """Build the prompt for keyword generation."""
        stocks_str = ", ".join(sector_stocks[:10])  # Limit to 10
        
        prompt = f"""请为板块"{sector_name}"生成 5-8 个关键词。

板块成分股（前 10 只）：{stocks_str}
"""
        if description:
            prompt += f"\n板块描述：{description}\n"
        
        prompt += """
请输出严格的 JSON 格式：
{
    "keywords": ["关键词 1", "关键词 2", "关键词 3", "关键词 4", "关键词 5"]
}

如果认为需要更多关键词，可以生成 6-8 个，但不要少于 5 个或超过 8 个。"""
        
        return prompt
    
    def _parse_keywords(self, response: str) -> List[str]:
        """Parse keywords from LLM response."""
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                keywords = data.get("keywords", [])
                
                # Validate
                if 5 <= len(keywords) <= 8:
                    return keywords
                else:
                    # Fallback: take first 5-8
                    return keywords[:8] if len(keywords) > 8 else keywords
            
            # Fallback: return empty
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse keywords: {e}")
            return []
```

### Task 2: Create keyword generation scheduler
**File**: `src/scheduler/jobs.py` (append)

```python
async def generate_sector_keywords_job():
    """
    Generate keywords for sectors without keywords.
    Runs weekly on Sunday at 10:00.
    """
    from src.market.keyword_generator import KeywordGenerator
    from src.market.sector_mapping import StockSectorService
    
    generator = KeywordGenerator()
    sector_service = StockSectorService()
    
    # Get sectors without keywords
    sectors = await get_sectors_without_keywords()
    
    for sector in sectors:
        stocks = await sector_service.get_sector_stocks(sector.sector_id)
        keywords = await generator.generate_keywords(
            sector_name=sector.sector_name,
            sector_stocks=stocks
        )
        
        if keywords:
            await save_sector_keywords(sector.sector_id, keywords)
            logger.info(f"Generated {len(keywords)} keywords for {sector.sector_name}")

# Schedule weekly
scheduler.add_job(
    generate_sector_keywords_job,
    trigger='cron',
    day_of_week='sun',
    hour=10,
    minute=0,
    id='sector_keyword_generation',
    name='Generate sector keywords weekly'
)
```

### Task 3: Create sector keywords table
**File**: `src/market/models.py` (append)

```python
class SectorKeywords(Base):
    """Sector keywords storage."""
    __tablename__ = "sector_keywords"
    
    id = Column(Integer, primary_key=True)
    sector_id = Column(String(50), nullable=False, unique=True, index=True)
    sector_name = Column(String(100))
    keywords = Column(JSON)  # List of 5-8 keywords
    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    generation_source = Column(String(50))  # "llm" or "manual"
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_sector_keywords.py` (create)

```python
def upgrade() -> None:
    op.create_table('sector_keywords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('sector_name', sa.String(100), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('generation_source', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sector_id')
    )
    
    op.create_index('idx_sector', 'sector_keywords', ['sector_id'])
```

### Task 5: Create unit tests
**File**: `tests/test_keyword_generator.py`

Test cases:
- Keyword generation (mock LLM)
- JSON parsing (valid response)
- JSON parsing (malformed response)
- Keyword count validation
- Scheduler integration

## Success Criteria
- [ ] KeywordGenerator service works
- [ ] LLM prompt produces valid JSON
- [ ] Keywords persisted correctly
- [ ] Weekly scheduler runs
- [ ] Unit tests pass

## Dependencies
- Phase 3: LLM client (completed)
- STOCK-01: Sector mappings (completed)

## Notes
- Keywords refreshed weekly
- Manual override supported
- Used for exposure calculation
