# -*- coding: utf-8 -*-
"""
OperationSuggester: generates trading suggestions based on tier classification.

Input:
  - Tier classification results (重点关注/观察名单/其余)
  - Skill files: composite/tier-thresholds.json

Process:
  1. For each tier, generate appropriate suggestion
  2. For individual stocks, generate specific action hints

Output:
  - List of suggestions with direction, position_size, stop_loss
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class OperationSuggester:
    """
    Generates trading suggestions based on tier classification.
    """

    TIER_SUGGESTIONS = {
        "重点关注": {
            "direction": "买入",
            "position_size": "主要仓位 (20-30%)",
            "stop_loss": "跌破 20 日均线止损",
            "time_horizon": "中期持有 (1-3 月)",
        },
        "观察名单": {
            "direction": "观察",
            "position_size": "试探性仓位 (5-10%)",
            "stop_loss": "跌破买入价 5% 止损",
            "time_horizon": "短期观察 (1-2 周)",
        },
        "其余": {
            "direction": "回避",
            "position_size": "不建仓",
            "stop_loss": "N/A",
            "time_horizon": "N/A",
        },
    }

    def __init__(self, skill_loader=None):
        self.skill_loader = skill_loader
        self._config = None

    def generate(self, tiers: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Generate trading suggestions for all tiers.

        Args:
            tiers: Dict of tier_name → list of stock dicts

        Returns:
            Dict with suggestions per tier and overall summary
        """
        logger.info("[OperationSuggester] generating suggestions")

        suggestions = {}
        for tier_name, stocks in tiers.items():
            tier_config = self.TIER_SUGGESTIONS.get(tier_name, self.TIER_SUGGESTIONS["其余"])

            stock_suggestions = []
            for stock in stocks:
                stock_code = stock.get("stock_code", "")
                recommend_score = stock.get("recommend_score", 0)

                stock_suggestion = {
                    "stock_code": stock_code,
                    "recommend_score": recommend_score,
                    "direction": tier_config["direction"],
                    "position_size": tier_config["position_size"],
                    "stop_loss": tier_config["stop_loss"],
                    "time_horizon": tier_config["time_horizon"],
                    "reason": stock.get("reason", ""),
                }
                stock_suggestions.append(stock_suggestion)

            suggestions[tier_name] = {
                "count": len(stocks),
                "direction": tier_config["direction"],
                "position_size": tier_config["position_size"],
                "stocks": stock_suggestions,
            }

        # Overall summary
        total = sum(s["count"] for s in suggestions.values())
        summary = {
            "total_stocks": total,
            "key_point_count": suggestions.get("重点关注", {}).get("count", 0),
            "watch_count": suggestions.get("观察名单", {}).get("count", 0),
            "other_count": suggestions.get("其余", {}).get("count", 0),
        }

        return {
            "suggestions": suggestions,
            "summary": summary,
        }
