"""Keyword generator service using LLM for sector keyword auto-generation.

STOCK-03: Keyword Auto-Generation
Generates 5-8 keywords for sectors using LLM.
"""

import json
import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.market.models import SectorKeywords
from src.logic.llm_service import LogicIdentificationService

logger = logging.getLogger(__name__)


class KeywordGenerator:
    """Generate keywords for sectors using LLM.

    This service uses LLM to generate 5-8 keywords for each sector.
    Keywords are used for:
    - Matching news and events to sectors
    - Linking sectors to investment logics
    - Calculating exposure coefficients

    The generator produces structured JSON output and handles parsing errors gracefully.
    """

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
        """Initialize keyword generator.

        Args:
            model: LLM model name to use for generation
        """
        self.model = model
        self.llm_service = LogicIdentificationService(model=model)

    async def generate_keywords(
        self,
        sector_name: str,
        sector_stocks: List[str],
        sector_description: Optional[str] = None
    ) -> List[str]:
        """Generate keywords for a sector.

        Args:
            sector_name: Sector name (e.g., "5G 概念")
            sector_stocks: List of constituent stock names
            sector_description: Optional sector description

        Returns:
            List of 5-8 keywords, or empty list if generation fails
        """
        logger.info(f"Generating keywords for sector: {sector_name}")

        prompt = self._build_prompt(sector_name, sector_stocks, sector_description)

        try:
            response = await self._call_llm(prompt)
            keywords = self._parse_keywords(response)

            if keywords:
                logger.info(f"Generated {len(keywords)} keywords for {sector_name}")
            else:
                logger.warning(f"No keywords generated for {sector_name}")

            return keywords

        except Exception as e:
            logger.error(f"Failed to generate keywords for {sector_name}: {e}")
            return []

    def _build_prompt(
        self,
        sector_name: str,
        sector_stocks: List[str],
        description: Optional[str]
    ) -> str:
        """Build the prompt for keyword generation.

        Args:
            sector_name: Sector name
            sector_stocks: List of stock names
            description: Optional description

        Returns:
            Formatted prompt string
        """
        # Limit to 10 stocks to avoid token limits
        stocks_str = ", ".join(sector_stocks[:10])

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

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for keyword generation.

        Args:
            prompt: The prompt to send to LLM

        Returns:
            Raw LLM response string
        """
        from litellm import acompletion

        try:
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _parse_keywords(self, response: str) -> List[str]:
        """Parse keywords from LLM response.

        Args:
            response: Raw LLM response string

        Returns:
            List of keywords, or empty list if parsing fails
        """
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                keywords = data.get("keywords", [])

                # Validate keyword count
                if not isinstance(keywords, list):
                    logger.warning("Keywords is not a list")
                    return []

                if len(keywords) < 5:
                    logger.warning(f"Too few keywords: {len(keywords)}")
                    # Still return them, caller can decide
                    return keywords[:8] if len(keywords) > 8 else keywords

                if len(keywords) > 8:
                    logger.info(f"Truncating {len(keywords)} keywords to 8")
                    return keywords[:8]

                return keywords

            # Fallback: try to parse entire response as JSON
            data = json.loads(response.strip())
            keywords = data.get("keywords", [])
            return keywords[:8] if len(keywords) > 8 else keywords

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse keywords: {e}, response: {response[:200]}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing keywords: {e}")
            return []


class SectorKeywordService:
    """Service for managing sector keywords persistence.

    Provides methods to:
    - Get sectors without keywords
    - Save generated keywords
    - Update existing keywords
    """

    async def _get_session(self) -> AsyncSession:
        """Get async session. Separated for testability."""
        return async_session_maker()

    async def get_sectors_without_keywords(self) -> List[dict]:
        """Get list of sectors that need keywords generated.

        Returns:
            List of dicts with sector_id and sector_name
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(SectorKeywords).where(
                    SectorKeywords.keywords.is_(None)
                )
            )
            records = result.scalars().all()
            return [{"sector_id": r.sector_id, "sector_name": r.sector_name} for r in records]

    async def save_keywords(
        self,
        sector_id: str,
        sector_name: str,
        keywords: List[str],
        source: str = "llm"
    ) -> bool:
        """Save keywords for a sector.

        Args:
            sector_id: Sector ID
            sector_name: Sector name
            keywords: List of keywords to save
            source: Generation source ("llm" or "manual")

        Returns:
            True if saved successfully, False otherwise
        """
        if not keywords:
            logger.warning("Attempted to save empty keywords")
            return False

        try:
            async with async_session_maker() as session:
                # Check if record exists
                result = await session.execute(
                    select(SectorKeywords).where(SectorKeywords.sector_id == sector_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.keywords = json.dumps(keywords, ensure_ascii=False)
                    existing.sector_name = sector_name
                    existing.updated_at = datetime.now()
                    existing.generation_source = source
                    logger.info(f"Updated keywords for sector {sector_id}")
                else:
                    # Insert new record
                    new_record = SectorKeywords(
                        sector_id=sector_id,
                        sector_name=sector_name,
                        keywords=json.dumps(keywords, ensure_ascii=False),
                        generation_source=source,
                    )
                    session.add(new_record)
                    logger.info(f"Inserted new keywords for sector {sector_id}")

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save keywords for {sector_id}: {e}")
            return False

    async def get_keywords(self, sector_id: str) -> Optional[List[str]]:
        """Get keywords for a sector.

        Args:
            sector_id: Sector ID

        Returns:
            List of keywords or None if not found
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(SectorKeywords).where(SectorKeywords.sector_id == sector_id)
            )
            record = result.scalar_one_or_none()

            if record and record.keywords:
                try:
                    return json.loads(record.keywords)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in keywords for {sector_id}")
                    return None
            return None


async def generate_sector_keywords_job():
    """Scheduled job to generate keywords for sectors without keywords.

    Runs weekly on Sunday at 10:00.
    Generates keywords using LLM and persists to database.
    """
    logger.info("Starting sector keyword generation job")

    generator = KeywordGenerator()
    keyword_service = SectorKeywordService()

    # Get sectors needing keywords
    sectors = await keyword_service.get_sectors_without_keywords()

    if not sectors:
        logger.info("No sectors need keyword generation")
        return

    logger.info(f"Found {len(sectors)} sectors needing keywords")

    for sector in sectors:
        sector_id = sector["sector_id"]
        sector_name = sector["sector_name"]

        # Get constituent stocks (placeholder - will be implemented in STOCK-01)
        # For now, use empty list - LLM can still generate generic keywords
        stocks = []

        try:
            keywords = await generator.generate_keywords(
                sector_name=sector_name,
                sector_stocks=stocks,
            )

            if keywords:
                success = await keyword_service.save_keywords(
                    sector_id=sector_id,
                    sector_name=sector_name,
                    keywords=keywords,
                    source="llm",
                )
                if success:
                    logger.info(f"Generated {len(keywords)} keywords for {sector_name}")
                else:
                    logger.error(f"Failed to save keywords for {sector_name}")
            else:
                logger.warning(f"No keywords generated for {sector_name}")

        except Exception as e:
            logger.error(f"Error generating keywords for {sector_name}: {e}")

    logger.info("Sector keyword generation job completed")
