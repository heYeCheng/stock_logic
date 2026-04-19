# -*- coding: utf-8 -*-
"""
RiskScanner: scans active logics against risk templates.

When a risk factor is triggered:
  1. Automatically downgrades the affected dimension score
  2. Recalculates logic_strength
  3. Adds entry to the issue queue
  4. May trigger flip detection if threshold breached

Skill-based: loads risk templates from SectorLogicSkillLoader.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .skill_loader import SectorLogicSkillLoader

logger = logging.getLogger(__name__)


class RiskScanner:
    """
    Scans all active trading logics against their risk templates.

    Called daily after data collection, before analysis output.
    """

    def __init__(self, skill_loader: Optional[SectorLogicSkillLoader] = None):
        self.skill_loader = skill_loader or SectorLogicSkillLoader()

    def scan(
        self,
        logics: List[Dict[str, Any]],
        d: date,
        signal_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan all active logics for risk triggers.

        Args:
            logics: list of TradingLogic dicts
            d: analysis date
            signal_data: collected signals (news, policy, etc.) for risk matching

        Returns:
            list of issue queue entries
        """
        issue_queue = []

        for logic in logics:
            category = logic.get("category")
            if not category:
                continue

            # Load risk template from skill file
            template = self.skill_loader.load_risk_template(category)
            if not template:
                continue

            logic_id = logic.get("logic_id", "unknown")
            sector = logic.get("sector", "unknown")
            current_strength = logic.get("logic_strength", 0.5)
            framework = logic.get("logic_strength_framework", {})

            for risk_factor in template.risk_factors:
                risk = risk_factor.risk
                source = risk_factor.source

                # TODO: implement actual signal matching against collected data
                triggered = self._check_risk_signal(risk, source, signal_data)

                if triggered:
                    # Downgrade affected dimension
                    downgraded = self._downgrade_dimension(framework, risk)

                    # Recalculate logic_strength
                    new_strength = self._recalc_strength(framework)
                    strength_drop = current_strength - new_strength

                    # Add to issue queue
                    entry = {
                        "sector": sector,
                        "logic_id": logic_id,
                        "risk_factor": risk,
                        "signal_summary": f"{risk} — 信号源：{source}",
                        "action": f"logic_strength 降 {strength_drop:.2f} 分",
                        "suggestion": risk_factor.suggestion,
                        "status": "active",
                        "detected_at": d.isoformat(),
                    }
                    issue_queue.append(entry)

                    # Update logic strength
                    logic["logic_strength"] = new_strength
                    logic["logic_strength_framework"] = framework

                    logger.info(
                        f"[RiskScanner] {logic_id}: risk triggered '{risk}'"
                        f", strength {current_strength:.2f} -> {new_strength:.2f}"
                    )

        return issue_queue

    def _check_risk_signal(
        self,
        risk_factor: str,
        source: str,
        signal_data: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Check if a risk factor's signal source has been triggered.

        TODO: implement actual signal matching against collected data.
        For now, returns False (no risks triggered by default).
        """
        if not signal_data:
            return False
        # Placeholder: implement actual signal matching logic
        return False

    def _downgrade_dimension(
        self,
        framework: Dict[str, Any],
        risk_factor: str,
    ) -> Dict[str, Any]:
        """
        Downgrade the dimension score that corresponds to the triggered risk.

        TODO: implement intelligent dimension matching based on risk type.
        For now, reduces the first dimension score by 2 points.
        """
        dimensions = framework.get("dimensions", [])
        if dimensions and isinstance(dimensions, list) and len(dimensions) > 0:
            first_dim = dimensions[0]
            if "score" in first_dim:
                first_dim["score"] = max(0, first_dim["score"] - 2)

        framework["dimensions"] = dimensions
        return framework

    def _recalc_strength(self, framework: Dict[str, Any]) -> float:
        """
        Recalculate logic_strength from framework dimensions.

        logic_strength = weighted_average(dimension_scores) / 10.0
        """
        dimensions = framework.get("dimensions", [])
        if not dimensions:
            return 0.5

        total_score = 0.0
        total_weight = 0.0

        for dim in dimensions:
            score = dim.get("score", 5)
            weight = dim.get("weight", 1.0)
            total_score += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        return round(total_score / total_weight / 10.0, 4)
