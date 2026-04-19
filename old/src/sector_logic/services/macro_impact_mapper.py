# -*- coding: utf-8 -*-
"""
MacroImpactMapper: maps macro analysis results to sector-level adjustments.

Phase 2.5 Enhanced:
- Version detection: config v1 uses old formula, v2 uses indicator-level formula
- v2 formula: sector_macro_adjustment = Σ(indicator_impact × indicator_sensitivity) / N
- Range truncation: -0.2 ~ +0.2
- Output includes indicator_breakdown showing per-indicator contribution

Input:
  - Macro analysis result (macro_thesis_score, macro_state, macro_radar)
  - Sector sensitivity config (macro/sector-sensitivity-config.json)

Output:
  - sector_adjustments: Dict[sector, {adjustment, indicator_breakdown}]
    - adjustment range: -0.2 to +0.2
    - Positive = favorable for sector
    - Negative = unfavorable for sector
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MacroImpactMapper:
    """
    Maps macro analysis results to sector-level adjustments.

    Phase 2.5: Supports both v1 (region-level) and v2 (indicator-level) formulas
    with automatic version detection.
    """

    def __init__(self, skill_loader):
        self.skill_loader = skill_loader
        self._config = None

    def _load_config(self) -> Dict[str, Any]:
        """Load sector sensitivity config from skill file."""
        if self._config:
            return self._config

        try:
            config = self.skill_loader._load_json_model("macro/sector-sensitivity-config.json")
            if config:
                self._config = config
                return self._config
        except Exception:
            pass

        skill_dir = self.skill_loader.skill_dir
        config_path = skill_dir / "macro" / "sector-sensitivity-config.json"
        if config_path.exists():
            self._config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self._config = {"sectors": [], "version": 1}

        return self._config

    def compute(
        self,
        macro_result: Dict[str, Any],
        sector_list: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compute sector-level macro adjustments.

        Auto-detects config version:
        - v1: region-level sensitivity → old formula
        - v2+: indicator-level sensitivity → new formula

        Returns Dict[sector, {sector_macro_adjustment, indicator_breakdown, ...}]
        """
        logger.info("[MacroImpactMapper] computing sector adjustments")

        config = self._load_config()
        version = config.get("version", 1)

        if version >= 2:
            return self._compute_v2(macro_result, sector_list, config)
        else:
            return self._compute_v1(macro_result, sector_list, config)

    def _compute_v1(
        self,
        macro_result: Dict[str, Any],
        sector_list: Optional[List[str]],
        config: Dict,
    ) -> Dict[str, Any]:
        """
        v1 formula: region-level sensitivity.

        adjustment = (macro_thesis_score - 0.5) × avg_sensitivity × 0.3
        Range: -0.15 to +0.15
        """
        sectors_config = config.get("sectors", [])
        macro_thesis_score = macro_result.get("macro_thesis_score", 0.5)

        sensitivity_map = {}
        description_map = {}
        for sector_cfg in sectors_config:
            sector_name = sector_cfg.get("sector", "")
            sensitivity_map[sector_name] = sector_cfg.get("sensitivity", {})
            description_map[sector_name] = sector_cfg.get("description", "")

        sectors_to_compute = sector_list if sector_list else list(sensitivity_map.keys())
        adjustments = {}

        for sector in sectors_to_compute:
            sensitivity = sensitivity_map.get(sector, {"china": 0.5, "us": 0.3, "global": 0.2})

            # Region-level sensitivity (old format)
            china_sens = sensitivity.get("china", 0.5)
            us_sens = sensitivity.get("us", 0.3)
            global_sens = sensitivity.get("global", 0.2)
            avg_sensitivity = (china_sens + us_sens + global_sens) / 3.0

            # Old formula
            adjustment = (macro_thesis_score - 0.5) * avg_sensitivity * 0.3
            adjustment = round(max(-0.15, min(0.15, adjustment)), 4)

            adjustments[sector] = {
                "sector_macro_adjustment": adjustment,
                "formula": "v1_region_level",
            }

        logger.info(
            f"[MacroImpactMapper] v1 computed {len(adjustments)} sectors"
        )
        return adjustments

    def _compute_v2(
        self,
        macro_result: Dict[str, Any],
        sector_list: Optional[List[str]],
        config: Dict,
    ) -> Dict[str, Any]:
        """
        v2 formula: indicator-level sensitivity.

        adjustment = Σ(indicator_impact × indicator_sensitivity) / N
        Range: -0.2 to +0.2

        indicator_impact = (dimension_score / 10 - 0.5)
          = deviation of dimension score from neutral (5.0/10 = 0.5)
          = range: -0.5 to +0.5

        indicator_sensitivity = from config (-1.0 to +1.0)
          = how much this sector responds to this indicator
          = positive: indicator improvement benefits sector
          = negative: indicator improvement harms sector
        """
        sectors_config = config.get("sectors", [])

        # Get macro radar scores (0-10 per dimension)
        macro_radar = macro_result.get("macro_radar", {})
        # Fallback: use macro_thesis_score if radar not available
        if not macro_radar:
            score = macro_result.get("macro_thesis_score", 0.5)
            macro_radar = {
                "liquidity_environment": score * 10,
                "economic_cycle_position": score * 10,
                "inflation_and_cost": score * 10,
                "policy_direction": score * 10,
                "global_linkage": score * 10,
            }

        # Build sector lookup
        sector_lookup = {}
        for sector_cfg in sectors_config:
            sector_name = sector_cfg.get("sector", "")
            sector_lookup[sector_name] = {
                "sensitivity": sector_cfg.get("sensitivity", {}),
                "description": sector_cfg.get("description", ""),
            }

        sectors_to_compute = sector_list if sector_list else list(sector_lookup.keys())
        adjustments = {}

        for sector in sectors_to_compute:
            sector_data = sector_lookup.get(sector, {})
            sensitivity = sector_data.get("sensitivity", {})

            if not sensitivity:
                # Unknown sector: skip or use neutral
                adjustments[sector] = {
                    "sector_macro_adjustment": 0.0,
                    "formula": "v2_indicator_level",
                    "indicator_breakdown": {},
                }
                continue

            result = self._compute_indicator_level_adjustment(
                sector, macro_radar, sensitivity
            )
            adjustments[sector] = result

        # Log summary
        positive = [s for s in adjustments if adjustments[s].get("sector_macro_adjustment", 0) > 0.02]
        negative = [s for s in adjustments if adjustments[s].get("sector_macro_adjustment", 0) < -0.02]
        logger.info(
            f"[MacroImpactMapper] v2 computed {len(adjustments)} sectors: "
            f"{len(positive)} positive, {len(negative)} negative"
        )

        return adjustments

    def _compute_indicator_level_adjustment(
        self,
        sector: str,
        macro_radar: Dict[str, float],
        sensitivity: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute indicator-level adjustment for a single sector.

        For each dimension in sensitivity:
        - If value is a dict: indicator-level sensitivity → compute per-indicator
        - If value is a number: dimension-level sensitivity → single contribution

        Returns:
        {
            "sector_macro_adjustment": float (-0.2 ~ +0.2),
            "indicator_breakdown": {dimension: {indicator: {impact, sensitivity, contribution}}},
            "formula": "v2_indicator_level",
        }
        """
        total_adjustment = 0.0
        indicator_breakdown: Dict[str, Any] = {}
        count = 0

        for dim_name, dim_value in sensitivity.items():
            # Get dimension score from macro radar (0-10)
            dim_score = macro_radar.get(dim_name, 5.0)
            # Impact: deviation from neutral (5.0 = neutral → 0.0 impact)
            dim_impact = (dim_score / 10.0) - 0.5  # range: -0.5 to +0.5

            if isinstance(dim_value, dict):
                # Indicator-level sensitivity (v2 format)
                dim_breakdown = {}
                for indicator_name, sens in dim_value.items():
                    contribution = dim_impact * sens
                    total_adjustment += contribution
                    count += 1
                    dim_breakdown[indicator_name] = {
                        "impact": round(dim_impact, 4),
                        "sensitivity": sens,
                        "contribution": round(contribution, 4),
                    }
                indicator_breakdown[dim_name] = dim_breakdown
            else:
                # Dimension-level sensitivity (fallback for v1-style values)
                contribution = dim_impact * dim_value
                total_adjustment += contribution
                count += 1
                indicator_breakdown[dim_name] = {
                    "impact": round(dim_impact, 4),
                    "sensitivity": dim_value,
                    "contribution": round(contribution, 4),
                }

        # Average across all indicator contributions
        if count > 0:
            total_adjustment /= count

        # Truncate to -0.2 ~ +0.2
        total_adjustment = max(-0.2, min(0.2, total_adjustment))

        return {
            "sector_macro_adjustment": round(total_adjustment, 4),
            "indicator_breakdown": indicator_breakdown,
            "formula": "v2_indicator_level",
        }

    def get_sector_sensitivity(self, sector: str) -> Dict[str, float]:
        """
        Get sensitivity config for a specific sector.

        Args:
            sector: Sector name

        Returns:
            Dict with sensitivity values
        """
        config = self._load_config()
        sectors_config = config.get("sectors", [])

        for sector_cfg in sectors_config:
            if sector_cfg.get("sector") == sector:
                return sector_cfg.get("sensitivity", {})

        return {}

    def get_most_sensitive_sectors(
        self, dimension_or_indicator: str, top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get sectors most sensitive to a specific dimension or indicator.

        Args:
            dimension_or_indicator: Dimension name (e.g., "liquidity_environment")
                                    or indicator name (e.g., "m1_m2_scissors")
            top_n: Number of sectors to return

        Returns:
            List of {sector, sensitivity, description} dicts, sorted by sensitivity descending
        """
        config = self._load_config()
        sectors_config = config.get("sectors", [])

        sensitive_sectors = []
        for sector_cfg in sectors_config:
            sector = sector_cfg.get("sector", "")
            sensitivity = sector_cfg.get("sensitivity", {})
            description = sector_cfg.get("description", "")

            # Search for the target in sensitivity config
            max_sens = 0.0
            if dimension_or_indicator in sensitivity:
                # Direct dimension match
                val = sensitivity[dimension_or_indicator]
                if isinstance(val, dict):
                    max_sens = max(abs(v) for v in val.values()) if val else 0.0
                else:
                    max_sens = abs(val)
            else:
                # Search within dimension dicts for indicator
                for dim_name, dim_value in sensitivity.items():
                    if isinstance(dim_value, dict) and dimension_or_indicator in dim_value:
                        max_sens = abs(dim_value[dimension_or_indicator])
                        break

            sensitive_sectors.append({
                "sector": sector,
                "sensitivity": max_sens,
                "description": description,
            })

        sensitive_sectors.sort(key=lambda x: x["sensitivity"], reverse=True)
        return sensitive_sectors[:top_n]
