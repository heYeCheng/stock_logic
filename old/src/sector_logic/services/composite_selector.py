# -*- coding: utf-8 -*-
"""
CompositeSelector: three-layer score combination and tier classification.

Input:
  - Macro result (macro_thesis_score, macro_state)
  - Sector results (sector_logic_strength, sector_adjustments)
  - Stock results (stock_thesis_score, radar_scores, tier)
  - Skill files: composite/weighting-config.json, composite/tier-thresholds.json, composite/macro-switch-rules.json

Process:
  1. Load weighting config (stock×0.5 + sector×0.3 + macro×0.2)
  2. Check macro switch: macro_thesis_score < 0.3 → trigger downgrade
  3. Compute composite score for each stock
  4. Apply macro switch downgrade if triggered
  5. Classify into tiers

Output:
  - Composite recommendations with recommend_score
  - Macro switch status (triggered/not_triggered)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CompositeSelector:
    """
    Combines three-layer scores and applies macro switch logic.
    """

    def __init__(self, skill_loader):
        self.skill_loader = skill_loader
        self._weighting_config = None
        self._tier_thresholds = None
        self._macro_switch_rules = None

    def _load_weighting_config(self) -> Dict[str, Any]:
        if self._weighting_config:
            return self._weighting_config
        self._weighting_config = self.skill_loader.load_composite_config("weighting-config.json")
        if not self._weighting_config:
            self._weighting_config = self._get_default_weighting()
        return self._weighting_config

    def _load_tier_thresholds(self) -> Dict[str, Any]:
        if self._tier_thresholds:
            return self._tier_thresholds
        self._tier_thresholds = self.skill_loader.load_composite_config("tier-thresholds.json")
        if not self._tier_thresholds:
            self._tier_thresholds = self._get_default_tier_thresholds()
        return self._tier_thresholds

    def _load_macro_switch_rules(self) -> Dict[str, Any]:
        if self._macro_switch_rules:
            return self._macro_switch_rules
        self._macro_switch_rules = self.skill_loader.load_composite_config("macro-switch-rules.json")
        if not self._macro_switch_rules:
            self._macro_switch_rules = self._get_default_macro_switch()
        return self._macro_switch_rules

    def _get_default_weighting(self) -> Dict[str, Any]:
        return {"weights": {"stock": 0.5, "sector": 0.3, "macro": 0.2}}

    def _get_default_tier_thresholds(self) -> Dict[str, Any]:
        return {
            "重点关注": {"min_recommend_score": 0.7},
            "观察名单": {"min_recommend_score": 0.5},
            "其余": {"default": True},
        }

    def _get_default_macro_switch(self) -> Dict[str, Any]:
        return {
            "triggers": [{"condition": "macro_thesis_score < 0.3", "threshold": 0.3}],
            "downgrade_actions": [
                {"action": "降低一级 tier"},
                {"action": "仓位减半"},
            ],
        }

    def select(
        self,
        macro_result: Dict[str, Any],
        sector_results: Dict[str, Any],
        stock_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run composite selection pipeline.

        Args:
            macro_result: Result from MacroAnalyzer
            sector_results: Dict of sector_name → sector_result
            stock_results: List of stock result dicts

        Returns:
            Dict with recommendations, macro_switch_status, tiers
        """
        logger.info("[CompositeSelector] running composite selection")

        weights = self._load_weighting_config().get("weights", {})
        stock_weight = weights.get("stock", 0.5)
        sector_weight = weights.get("sector", 0.3)
        macro_weight = weights.get("macro", 0.2)

        # 1. Macro switch check
        macro_switch = self._check_macro_switch(macro_result)

        # 2. Compute composite scores
        recommendations = []
        for stock in stock_results:
            stock_code = stock.get("stock_code", "")
            stock_thesis = stock.get("stock_thesis_score", 0.5)
            sector_name = stock.get("sector", "")
            sector_result = sector_results.get(sector_name, {})
            sector_logic = sector_result.get("sector_logic_strength", 0.5)
            macro_adj = sector_result.get("sector_macro_adjustment", 0.0)

            # Composite score: stock×0.5 + sector×0.3 + macro×0.2
            macro_component = macro_result.get("macro_thesis_score", 0.5) + macro_adj
            recommend_score = (
                stock_thesis * stock_weight
                + sector_logic * sector_weight
                + macro_component * macro_weight
            )
            recommend_score = round(max(0.0, min(1.0, recommend_score)), 4)

            recommendations.append({
                **stock,
                "recommend_score": recommend_score,
                "stock_thesis_score": stock_thesis,
                "sector_logic_strength": sector_logic,
                "macro_component": round(macro_component, 4),
            })

        # 3. Apply macro switch downgrade
        if macro_switch["triggered"]:
            recommendations = self._apply_macro_downgrade(recommendations, macro_switch)
            logger.warning(f"[CompositeSelector] macro switch triggered, downgrading {len(recommendations)} stocks")

        # 4. Classify into tiers
        tiers = self._classify_tiers(recommendations)

        return {
            "recommendations": recommendations,
            "tiers": tiers,
            "macro_switch_status": macro_switch,
            "total_count": len(recommendations),
        }

    def _check_macro_switch(self, macro_result: Dict[str, Any]) -> Dict[str, Any]:
        """Check if macro switch should be triggered."""
        rules = self._load_macro_switch_rules()

        # Support flat format (from defaults) and nested format (from skill file)
        msr = rules.get("macro_switch_rules", rules)
        trigger_condition = msr.get("trigger_condition", {})
        downgrade_actions = msr.get("downgrade_actions", [])

        # Also check partial downgrade rules
        partial_rules = rules.get("partial_downgrade_rules", {})
        partial_condition = partial_rules.get("trigger_condition", {})

        macro_thesis_score = macro_result.get("macro_thesis_score", 0.5)

        # Full macro switch: score < 0.3
        full_threshold = trigger_condition.get("macro_thesis_score_threshold", 0.3)
        if macro_thesis_score < full_threshold:
            return {
                "triggered": True,
                "severity": "full",
                "reason": f"macro_thesis_score={macro_thesis_score:.2f} < threshold={full_threshold}",
                "downgrade_actions": downgrade_actions,
            }

        # Partial downgrade: score < 0.4
        partial_threshold = partial_condition.get("macro_thesis_score_threshold", 0.4)
        if macro_thesis_score < partial_threshold:
            partial_actions = partial_rules.get("actions", [])
            return {
                "triggered": True,
                "severity": "partial",
                "reason": f"macro_thesis_score={macro_thesis_score:.2f} < partial_threshold={partial_threshold}",
                "downgrade_actions": partial_actions,
            }

        return {"triggered": False, "severity": "none", "reason": "macro environment normal", "downgrade_actions": []}

    def _apply_macro_downgrade(self, recommendations: List[Dict], macro_switch: Dict[str, Any]) -> List[Dict]:
        """Apply macro switch downgrade to recommendations."""
        severity = macro_switch.get("severity", "full")

        if severity == "partial":
            # Partial: only reduce score
            haircut = 0.1
            for rec in recommendations:
                rec["recommend_score"] = round(max(0, rec.get("recommend_score", 0) - haircut), 4)
            return recommendations

        # Full: tier downgrade + score haircut
        for rec in recommendations:
            current_tier = rec.get("tier", "其余")
            # Downgrade one tier
            if current_tier == "重点关注":
                rec["tier"] = "观察名单"
                rec["downgrade_reason"] = "macro switch triggered"
            elif current_tier == "观察名单":
                rec["tier"] = "其余"
                rec["downgrade_reason"] = "macro switch triggered"
            # 其余 stays 其余
            rec["recommend_score"] = round(rec.get("recommend_score", 0) * 0.8, 4)

        return recommendations

    def _classify_tiers(self, recommendations: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify recommendations into tiers."""
        thresholds = self._load_tier_thresholds()

        tiers = {"重点关注": [], "观察名单": [], "其余": []}

        key_point_threshold = thresholds.get("重点关注", {}).get("min_recommend_score", 0.7)
        watch_threshold = thresholds.get("观察名单", {}).get("min_recommend_score", 0.5)

        # Sort by recommend_score descending
        sorted_recs = sorted(recommendations, key=lambda x: x.get("recommend_score", 0), reverse=True)

        for rec in sorted_recs:
            score = rec.get("recommend_score", 0)
            tier = rec.get("tier", None)

            if tier is None:
                # Classify by score
                if score >= key_point_threshold:
                    tier = "重点关注"
                elif score >= watch_threshold:
                    tier = "观察名单"
                else:
                    tier = "其余"

            tiers.setdefault(tier, []).append(rec)

        return tiers
