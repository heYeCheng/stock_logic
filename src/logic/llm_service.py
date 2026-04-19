"""LLM service for logic identification - Stage 1 of the pipeline."""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import LogicModel, LogicDirection, ImportanceLevel

logger = logging.getLogger(__name__)


class LogicIdentificationService:
    """Stage 1: Identify logics from news text.

    This service takes news articles and extracts investment logics using LLM.
    Output is structured logic schemas that can be used for event extraction.
    """

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

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    async def identify_logics(
        self,
        news_text: str,
        source: str = None
    ) -> List[LogicModel]:
        """Identify logics from news text.

        Args:
            news_text: News article text in Chinese
            source: Optional source identifier

        Returns:
            List of LogicModel instances (persisted to database)
        """
        logger.info(f"Identifying logics from news (source={source})")

        # Call LLM
        response_json = await self._call_llm(news_text)

        # Parse and validate
        logics = self._parse_response(response_json)

        # Deduplicate and persist
        persisted = await self._save_logics(logics)

        logger.info(f"Identified and persisted {len(persisted)} logics")
        return persisted

    async def _call_llm(self, news_text: str) -> Dict[str, Any]:
        """Call LLM for logic identification."""
        try:
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": news_text}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _parse_response(self, response: Dict[str, Any]) -> List[LogicModel]:
        """Parse LLM response into LogicModel instances."""
        logics = []

        for item in response.get("logics", []):
            try:
                # Validate required fields
                if not all(k in item for k in ["logic_id", "logic_family", "direction", "importance_level"]):
                    logger.warning(f"Missing required fields in logic: {item}")
                    continue

                # Validate confidence threshold
                confidence = item.get("confidence", 0.0)
                if confidence < 0.5:
                    logger.debug(f"Low confidence logic skipped: {item.get('logic_id')}")
                    continue

                logic = LogicModel(
                    logic_id=item["logic_id"],
                    logic_name=item.get("description", item["logic_id"]),
                    logic_family=item["logic_family"],
                    direction=LogicDirection[item["direction"]],
                    importance_level=ImportanceLevel[item["importance_level"]],
                    description=item.get("description", ""),
                    keywords=item.get("keywords", []),
                    validity_days=self._get_validity_days(item["logic_family"]),
                )
                logics.append(logic)

            except KeyError as e:
                logger.warning(f"Invalid logic format, missing {e}: {item}")
                continue

        return logics

    def _get_validity_days(self, logic_family: str) -> int:
        """Get default validity days by logic family."""
        validity_map = {
            "technology": 45,
            "policy": 60,
            "earnings": 21,
            "m_a": 30,
            "supply_chain": 30,
        }
        return validity_map.get(logic_family, 30)

    async def _save_logics(self, logics: List[LogicModel]) -> List[LogicModel]:
        """Save logics to database, skipping duplicates."""
        persisted = []

        async with async_session_maker() as session:
            for logic in logics:
                # Check if logic_id exists
                result = await session.execute(
                    select(LogicModel).where(LogicModel.logic_id == logic.logic_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing logic
                    self._merge_logic(existing, logic)
                    persisted.append(existing)
                    logger.debug(f"Updated existing logic: {logic.logic_id}")
                else:
                    # Insert new logic
                    session.add(logic)
                    persisted.append(logic)
                    logger.info(f"Inserted new logic: {logic.logic_id}")

            await session.commit()

        return persisted

    def _merge_logic(self, existing: LogicModel, new: LogicModel) -> None:
        """Merge new logic data into existing logic."""
        # Update fields that may have new information
        if new.description:
            existing.description = new.description
        if new.keywords:
            # Merge keywords
            existing_keywords = existing.keywords or []
            existing.keywords = list(set(existing_keywords + new.keywords))
        existing.updated_at = datetime.now()
