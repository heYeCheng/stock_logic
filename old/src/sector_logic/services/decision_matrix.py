# -*- coding: utf-8 -*-
"""
DecisionMatrix: classifies stocks into tiers based on thesis_score and Buffett filter.

Input:
  - stock_thesis_score (0-1)
  - buffett_filter_result (pass/pass_with_concerns/fail)
  - Stock metadata (listing_date, is_st, is_suspended)
  - Skill files: stock/decision-matrix.json

Process:
  1. Load decision matrix config
  2. Check special cases (ST, suspended, new listed)
  3. Apply tier thresholds
  4. Apply Buffett filter override
  5. Generate tier classification with action hint

Output:
  - tier: 重点关注/观察名单/其余
  - action_hint: buy/watch/ignore
  - reason: explanation of classification
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DecisionMatrix:
    """
    Classifies stocks into tiers based on composite score and qualitative filter.
    """

    TIERS = ["重点关注", "观察名单", "其余"]

    def __init__(self, skill_loader):
        self.skill_loader = skill_loader
        self._config = None

    def _load_config(self) -> Dict[str, Any]:
        """Load decision matrix config."""
        if self._config:
            return self._config

        self._config = self.skill_loader.load_stock_config("decision-matrix.json")
        if not self._config:
            self._config = self._get_default_config()

        return self._config

    def _get_default_config(self) -> Dict[str, Any]:
        """Default config if skill file not found."""
        return {
            "tier_thresholds": {
                "重点关注": {"min_stock_thesis_score": 0.7, "buffett_filter": "pass"},
                "观察名单": {"min_stock_thesis_score": 0.5},
                "其余": {"default": True},
            },
            "buffett_filter_override": {
                "rules": [
                    {"condition": "buffett_filter = fail", "action": "其余"},
                    {"condition": "buffett_filter = pass_with_concerns", "max_tier": "观察名单"},
                ]
            },
            "special_cases": {},
        }

    def classify(
        self,
        stock_code: str,
        stock_thesis_score: float,
        buffett_result: str = "pass",
        stock_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Classify stock into a tier.

        Args:
            stock_code: Stock ticker
            stock_thesis_score: Overall score (0-1)
            buffett_result: Result from BuffettFilter ("pass"/"pass_with_concerns"/"fail")
            stock_metadata: Optional metadata (listing_date, is_st, is_suspended)

        Returns:
            Dict with tier, action_hint, color, reason
        """
        logger.info(f"[DecisionMatrix] classifying {stock_code} (score={stock_thesis_score:.2f})")

        config = self._load_config()

        # 1. Check special cases first
        special_tier = self._check_special_cases(stock_code, stock_metadata)
        if special_tier:
            return self._build_result(
                tier=special_tier,
                stock_code=stock_code,
                stock_thesis_score=stock_thesis_score,
                reason=f"Special case: {special_tier}",
            )

        # 2. Determine tier based on score
        tier = self._determine_tier_by_score(stock_thesis_score)

        # 3. Apply Buffett filter override
        tier = self._apply_buffett_override(tier, buffett_result)

        # 4. Build result
        return self._build_result(
            tier=tier,
            stock_code=stock_code,
            stock_thesis_score=stock_thesis_score,
            buffett_result=buffett_result,
        )

    def _check_special_cases(
        self,
        stock_code: str,
        stock_metadata: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Check if stock matches any special case."""
        if not stock_metadata:
            return None

        # ST stock → 其余
        if stock_metadata.get("is_st", False):
            logger.info(f"[DecisionMatrix] {stock_code} is ST, classified as 其余")
            return "其余"

        # Suspended → None (exclude from selection)
        if stock_metadata.get("is_suspended", False):
            logger.info(f"[DecisionMatrix] {stock_code} is suspended, excluded")
            return "其余"

        # New listed stock
        listing_date = stock_metadata.get("listing_date")
        if listing_date:
            today = date.today()
            days_listed = (today - listing_date).days
            if days_listed < 180:  # < 6 months
                return "其余"

        return None

    def _determine_tier_by_score(self, stock_thesis_score: float) -> str:
        """Determine tier based on score thresholds."""
        config = self._load_config()
        thresholds = config.get("tier_thresholds", {})

        # Check 重点关注
        key_point = thresholds.get("重点关注", {})
        if stock_thesis_score >= key_point.get("min_stock_thesis_score", 0.7):
            return "重点关注"

        # Check 观察名单
        watch = thresholds.get("观察名单", {})
        if stock_thesis_score >= watch.get("min_stock_thesis_score", 0.5):
            return "观察名单"

        # Default: 其余
        return "其余"

    def _apply_buffett_override(self, tier: str, buffett_result: str) -> str:
        """Apply Buffett filter override."""
        if buffett_result == "fail":
            return "其余"
        elif buffett_result == "pass_with_concerns":
            if tier == "重点关注":
                return "观察名单"
        return tier

    def _build_result(
        self,
        tier: str,
        stock_code: str,
        stock_thesis_score: float,
        buffett_result: str = None,
        reason: str = None,
    ) -> Dict[str, Any]:
        """Build classification result."""
        config = self._load_config()
        thresholds = config.get("tier_thresholds", {})
        tier_config = thresholds.get(tier, {})

        action_hints = {
            "重点关注": "可建立主要仓位",
            "观察名单": "加入自选，等待回调",
            "其余": "保持观察或忽略",
        }

        colors = {
            "重点关注": "red",
            "观察名单": "orange",
            "其余": "gray",
        }

        descriptions = {
            "重点关注": "强烈推荐，优先配置",
            "观察名单": "值得观察，等待更好买点",
            "其余": "暂不关注或存在明显缺陷",
        }

        if reason is None:
            if buffett_result == "fail":
                reason = "Buffett 定性过滤器未通过"
            elif buffett_result == "pass_with_concerns" and tier == "观察名单":
                reason = f"score={stock_thesis_score:.2f}, Buffett 存在一定担忧 → 降级至观察名单"
            else:
                reason = descriptions.get(tier, "")

        return {
            "stock_code": stock_code,
            "tier": tier,
            "stock_thesis_score": stock_thesis_score,
            "action_hint": tier_config.get("action_hint", action_hints.get(tier, "")),
            "color": tier_config.get("color", colors.get(tier, "gray")),
            "description": tier_config.get("description", descriptions.get(tier, "")),
            "reason": reason,
            "buffett_filter_result": buffett_result,
        }
