# -*- coding: utf-8 -*-
"""
StrengthEvaluator: evaluates logic strength using framework dimensions.

Input:
  - TradingLogic (from LogicExtractor)
  - Sector data
  - Skill files: logics/{category}/framework.json (5 dimensions)

Process:
  1. Load evaluation framework for the logic category
  2. Evaluate each dimension (0-10 score) using data + LLM
  3. Compute weighted average → logic_strength (0-1)

Output:
  - Updated TradingLogic with:
    - logic_strength (0-1)
    - logic_strength_framework (dimensions with scores)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StrengthEvaluator:
    """
    Evaluates logic strength using framework dimensions.

    Supports:
    - Rule-based scoring (MVP)
    - LLM-based scoring (future)
    """

    def __init__(self, skill_loader, llm_client=None):
        self.skill_loader = skill_loader
        self.llm_client = llm_client
        self._framework_cache = {}

    def _load_framework(self, category: str) -> Optional[Dict[str, Any]]:
        """Load evaluation framework for a logic category."""
        if category in self._framework_cache:
            return self._framework_cache[category]

        framework = self.skill_loader.load_framework(category)
        if framework:
            # Convert Pydantic model to dict
            framework_dict = {
                "logic_type": framework.logic_type,
                "version": framework.version,
                "dimensions": [
                    {
                        "name": dim.name,
                        "weight": dim.weight,
                        "data_source": dim.data_source,
                        "scoring_prompt": dim.scoring_prompt,
                    }
                    for dim in framework.dimensions
                ],
            }
            self._framework_cache[category] = framework_dict
            return framework_dict

        return None

    async def evaluate(
        self,
        logic: Dict[str, Any],
        sector_data: Dict[str, Any],
        macro_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate logic strength.

        Args:
            logic: TradingLogic dict (from LogicExtractor)
            sector_data: Sector data (index, capital flow, news)
            macro_context: Optional macro context

        Returns:
            Updated TradingLogic with logic_strength and framework scores
        """
        category = logic.get("category", "供需周期")

        logger.info(f"[StrengthEvaluator] evaluating {category} logic for {logic.get('sector', 'unknown')}")

        # Load framework
        framework = self._load_framework(category)
        if not framework:
            logger.warning(f"[StrengthEvaluator] framework not found for {category}, using default")
            framework = self._get_default_framework(category)

        # Evaluate dimensions
        if self.llm_client:
            try:
                return await self._evaluate_with_llm(logic, sector_data, framework, macro_context)
            except Exception as e:
                logger.warning(f"[StrengthEvaluator] LLM evaluation failed: {e}, falling back to rules")

        # Rule-based fallback
        return self._evaluate_with_rules(logic, sector_data, framework, macro_context)

    def _get_default_framework(self, category: str) -> Dict[str, Any]:
        """Get default framework for unknown categories."""
        return {
            "logic_type": category,
            "version": 1,
            "dimensions": [
                {"name": "基本面", "weight": 0.25, "data_source": "财务数据"},
                {"name": "技术面", "weight": 0.25, "data_source": "量价数据"},
                {"name": "资金面", "weight": 0.2, "data_source": "资金流向"},
                {"name": "情绪面", "weight": 0.15, "data_source": "新闻情绪"},
                {"name": "逻辑面", "weight": 0.15, "data_source": "逻辑强度"},
            ],
        }

    async def _evaluate_with_llm(
        self,
        logic: Dict[str, Any],
        sector_data: Dict[str, Any],
        framework: Dict[str, Any],
        macro_context: Optional[Dict],
    ) -> Dict[str, Any]:
        """LLM-based dimension evaluation."""
        # Build prompt for each dimension
        # Call LLM for scoring
        # For now, fall back to rule-based
        return self._evaluate_with_rules(logic, sector_data, framework, macro_context)

    def _evaluate_with_rules(
        self,
        logic: Dict[str, Any],
        sector_data: Dict[str, Any],
        framework: Dict[str, Any],
        macro_context: Optional[Dict],
    ) -> Dict[str, Any]:
        """Rule-based dimension scoring (MVP)."""
        dimensions = framework.get("dimensions", [])
        sector_index = sector_data.get("sector_index", {})
        capital_flow = sector_data.get("capital_flow", {})
        news = sector_data.get("news_items", [])

        pct_chg = sector_index.get("pct_chg", 0)
        net_flow = capital_flow.get("net_flow", 0)

        # Score each dimension
        scored_dimensions = []
        for dim in dimensions:
            dim_name = dim.get("name", "")
            score = self._score_dimension(dim_name, pct_chg, net_flow, news, sector_data)
            scored_dimensions.append({
                "name": dim_name,
                "weight": dim.get("weight", 0.2),
                "data_source": dim.get("data_source", ""),
                "score": score,
            })

        # Compute weighted average
        total_score = sum(d["score"] * d["weight"] for d in scored_dimensions)
        total_weight = sum(d["weight"] for d in scored_dimensions)

        if total_weight > 0:
            logic_strength = (total_score / total_weight) / 10.0  # Normalize to 0-1
        else:
            logic_strength = 0.5

        logic_strength = max(0.0, min(1.0, logic_strength))

        # Update logic dict
        logic["logic_strength"] = round(logic_strength, 4)
        logic["logic_strength_framework"] = scored_dimensions

        logger.info(f"[StrengthEvaluator] {logic.get('sector')} logic_strength={logic_strength:.2f}")
        return logic

    def _score_dimension(
        self,
        dim_name: str,
        pct_chg: float,
        net_flow: float,
        news: List[Dict],
        sector_data: Dict[str, Any],
    ) -> float:
        """Score a single dimension (0-10)."""
        # Default neutral score
        score = 5.0

        if "需求" in dim_name or "供给" in dim_name or "基本面" in dim_name:
            # Supply/demand: price + flow
            if pct_chg > 2 and net_flow > 2000:
                score = 8.0
            elif pct_chg > 0 and net_flow > 0:
                score = 6.5
            elif pct_chg < 0 and net_flow < 0:
                score = 3.5
            else:
                score = 5.0

        elif "资金" in dim_name or "流动性" in dim_name:
            # Capital flow
            if net_flow > 5000:
                score = 9.0
            elif net_flow > 2000:
                score = 7.5
            elif net_flow > 0:
                score = 6.0
            elif net_flow > -2000:
                score = 4.0
            else:
                score = 2.5

        elif "技术" in dim_name or "量价" in dim_name:
            # Technical: price action
            if pct_chg > 3:
                score = 8.5
            elif pct_chg > 1:
                score = 7.0
            elif pct_chg > -1:
                score = 5.0
            elif pct_chg > -3:
                score = 3.5
            else:
                score = 2.0

        elif "情绪" in dim_name:
            # Sentiment: news count
            news_count = len(news)
            if news_count > 10:
                score = 8.0
            elif news_count > 5:
                score = 6.5
            elif news_count > 2:
                score = 5.5
            else:
                score = 4.5

        elif "逻辑" in dim_name or "竞争" in dim_name:
            # Logic strength: default to neutral
            score = 5.5

        elif "政策" in dim_name:
            # Policy: check news for policy keywords
            policy_keywords = ["政策", "扶持", "利好", "规划", "指导意见"]
            policy_count = sum(
                1 for n in news
                if any(kw in (n.get("title", "") or "") for kw in policy_keywords)
            )
            if policy_count > 3:
                score = 8.0
            elif policy_count > 1:
                score = 6.5
            else:
                score = 5.0

        else:
            # Unknown dimension: neutral
            score = 5.0

        return max(0.0, min(10.0, score))
