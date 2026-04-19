# -*- coding: utf-8 -*-
"""
LogicEngine: L1 logic identification and management for Phase 0.5.

Uses LLM to identify trading logics for sectors, then maps importance levels
to initial strengths via anchor files. The LLM never assigns numeric scores —
it only outputs qualitative labels (高/中/低) that the rule engine maps.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Importance level → initial strength mapping (overridden by anchors)
DEFAULT_IMPORTANCE_MAP = {
    '高': 0.7,
    '中': 0.5,
    '低': 0.3,
}

LOGIC_IDENTIFICATION_PROMPT = """板块名称：{sector_name}
板块描述：{sector_description}
近期相关信息（无价格数据）：
{context_info}

请分析当前影响该板块的主要交易逻辑，每条逻辑输出：
1. logic_id: 唯一标识（如 "gold_rate_cut_2026Q2"）
2. title: 一句话标题
3. description: 2-3句描述
4. direction: "positive" 或 "negative"
5. category: "产业趋势" / "政策驱动" / "事件驱动" / "流动性驱动" 四选一
6. evidence_summary: 不超过3条支持证据
7. catalyst_events: 不超过3条催化剂事件
8. importance_level: "高" / "中" / "低"

评分参考锚点:
- 高：该逻辑能解释板块内多数龙头股近20日走势，有≥3条独立证据，市场共识度高
- 中：能解释板块内部分龙头股走势，有1-2条独立证据，市场有一定共识
- 低：仅影响个别个股，证据单一或存疑，市场共识模糊

逻辑族分类锚点:
- 产业趋势：由行业供需变化、技术迭代、产品周期驱动的长期逻辑
- 政策驱动：由国家/部委政策直接引发的逻辑
- 事件驱动：由突发事件、地缘冲突等驱动的短期逻辑
- 流动性驱动：由利率变化、资金面松紧驱动的逻辑

请按重要性排序，最多输出3条正向、2条反向。
输出严格JSON数组。"""


class LogicEngine:
    """
    L1 Logic Engine (Phase 0.5).

    Identifies trading logics via LLM, maps importance to initial strength,
    and manages logic persistence.
    """

    def __init__(self, llm_client, anchor_loader=None, logic_repo=None):
        self.llm_client = llm_client
        self.anchor_loader = anchor_loader
        self.logic_repo = logic_repo
        self._importance_map = None

    def _get_importance_map(self) -> Dict[str, float]:
        """Load importance mapping from anchor."""
        if self._importance_map is None:
            if self.anchor_loader:
                data = self.anchor_loader.load('logic_importance.yaml')
                levels = data.get('levels', {})
                self._importance_map = {
                    '高': levels.get('high', {}).get('initial_strength', 0.7),
                    '中': levels.get('medium', {}).get('initial_strength', 0.5),
                    '低': levels.get('low', {}).get('initial_strength', 0.3),
                }
            else:
                self._importance_map = DEFAULT_IMPORTANCE_MAP.copy()
        return self._importance_map

    async def identify_logics(self, sector_code: str, sector_name: str,
                              sector_description: str,
                              context_info: str = "",
                              max_positive: int = 3,
                              max_negative: int = 2) -> List[Dict[str, Any]]:
        """
        Call LLM to identify trading logics for a sector.

        Args:
            sector_code: Sector code (e.g. "CPO")
            sector_name: Sector name
            sector_description: Sector description
            context_info: Additional context (macro, industry, policy events)
            max_positive: Max positive logics to identify
            max_negative: Max negative logics to identify

        Returns:
            List of identified logics with initial_strength mapped from importance_level
        """
        prompt = LOGIC_IDENTIFICATION_PROMPT.format(
            sector_name=sector_name,
            sector_description=sector_description,
            context_info=context_info or "无额外信息",
        )

        importance_map = self._get_importance_map()
        result_logics = []

        try:
            if hasattr(self.llm_client, 'chat'):
                response = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                raw_text = response.get("content", "")
            else:
                logger.warning("[LogicEngine] LLM client has no chat method, returning empty")
                return []

            # Parse JSON from response
            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```json", 1)[-1].split("```")[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:].strip()

            logics = json.loads(raw_text)
            if not isinstance(logics, list):
                logics = [logics]

            for logic in logics[:max_positive + max_negative]:
                importance = logic.get('importance_level', '中')
                initial_strength = importance_map.get(importance, importance_map['中'])

                logic_entry = {
                    'logic_id': logic.get('logic_id', self._generate_logic_id(sector_code, logic.get('title', ''))),
                    'sector_code': sector_code,
                    'title': logic.get('title', ''),
                    'description': logic.get('description', ''),
                    'direction': logic.get('direction', 'positive'),
                    'category': logic.get('category', '事件驱动'),
                    'importance_level': importance,
                    'initial_strength': initial_strength,
                    'evidence_summary': logic.get('evidence_summary', ''),
                    'catalyst_events': logic.get('catalyst_events', []),
                }
                result_logics.append(logic_entry)

                # Save to repo
                if self.logic_repo:
                    self.logic_repo.save(
                        logic_id=logic_entry['logic_id'],
                        sector_code=sector_code,
                        title=logic_entry['title'],
                        description=logic_entry['description'],
                        direction=logic_entry['direction'],
                        category=logic_entry['category'],
                        importance_level=importance,
                        initial_strength=initial_strength,
                    )

        except Exception as e:
            logger.error(f"[LogicEngine] Logic identification failed: {e}")
            # Return existing logics if available
            if self.logic_repo:
                existing = self.logic_repo.get_by_sector(sector_code)
                if existing:
                    logger.info(f"[LogicEngine] Using {len(existing)} existing logics for {sector_code}")
                    return [self.logic_repo.to_dict(l) for l in existing]

        logger.info(f"[LogicEngine] Identified {len(result_logics)} logics for {sector_code}")
        return result_logics

    def _generate_logic_id(self, sector_code: str, title: str) -> str:
        """Generate a unique logic_id."""
        content = f"{sector_code}_{title}"
        return f"{sector_code}_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def get_active_logics(self, sector_code: str) -> List[Dict[str, Any]]:
        """Get all active logics for a sector."""
        if not self.logic_repo:
            return []
        logics = self.logic_repo.get_by_sector(sector_code)
        return [self.logic_repo.to_dict(l) for l in logics]
