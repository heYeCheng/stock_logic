# -*- coding: utf-8 -*-
"""
EventTriggerDetector: detects whether macro event triggers immediate re-run.

Trigger rules (from macro/state-classification.json):
- Fed rate change > 25BP
- China RRR cut / rate cut
- Tariff policy major change
- Geopolitical conflict escalation
- Polymarket probability change > 20%
- PMI surprise > 2 points
- Nonfarm surprise > 100k

Usage:
  detector = EventTriggerDetector(skill_loader, datastore)
  triggered = await detector.check(d, new_data, last_data)
  if triggered:
      await macro_analyzer.run(d)  # immediate re-run
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EventTriggerDetector:
    """
    Detects macro events that trigger immediate re-run of MacroAnalyzer.
    """

    def __init__(self, skill_loader, datastore):
        self.skill_loader = skill_loader
        self.datastore = datastore
        self._config = None

    def _load_config(self) -> Dict[str, Any]:
        """Load event trigger rules from skill file."""
        if self._config:
            return self._config

        # Try to load via skill_loader
        try:
            config = self.skill_loader._load_json_model(
                "macro/state-classification.json",
                type("MockModel", (), {"__init__": lambda self, **kwargs: setattr(self, "__dict__", kwargs)})
            )
            if config:
                self._config = config.__dict__
                return self._config
        except Exception:
            pass

        # Fallback: load directly from file
        import json
        from pathlib import Path
        skill_dir = Path("~/.gstack/skills/sector-logic").expanduser()
        config_path = skill_dir / "macro" / "state-classification.json"
        if config_path.exists():
            self._config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self._config = {"event_triggered_update_rules": {"rules": []}}

        return self._config

    async def check(self, d: date, new_data: Dict, last_data: Optional[Dict]) -> bool:
        """
        Check if any macro event triggers immediate re-run.

        Args:
            d: Analysis date
            new_data: Newly collected macro data
            last_data: Last macro data snapshot (for comparison)

        Returns:
            True if re-run triggered, False otherwise
        """
        if not last_data:
            logger.info("[EventTriggerDetector] no last data, skipping event check")
            return False

        config = self._load_config()
        rules = config.get("event_triggered_update_rules", {}).get("rules", [])

        for rule in rules:
            triggered = await self._check_rule(rule, new_data, last_data)
            if triggered:
                logger.info(f"[EventTriggerDetector] event triggered: {rule.get('id', 'unknown')} - {rule.get('trigger', 'unknown')}")
                return True

        return False

    async def _check_rule(self, rule: Dict, new_data: Dict, last_data: Dict) -> bool:
        """Check single trigger rule."""
        trigger_id = rule.get("id", "")
        threshold = rule.get("threshold")

        if "fed_rate" in trigger_id or "fed" in trigger_id.lower():
            return self._check_fed_rate_change(new_data, last_data, threshold)
        elif "china_rate" in trigger_id or "china" in trigger_id.lower():
            return self._check_china_rate_change(new_data, last_data, threshold)
        elif "tariff" in trigger_id:
            return self._check_tariff_change(new_data, last_data)
        elif "geopolitical" in trigger_id or "conflict" in trigger_id:
            return self._check_geopolitical_change(new_data, last_data)
        elif "polymarket" in trigger_id:
            return self._check_polymarket_change(new_data, last_data, threshold)
        elif "pmi" in trigger_id:
            return self._check_pmi_surprise(new_data, last_data, threshold)
        elif "nonfarm" in trigger_id:
            return self._check_nonfarm_surprise(new_data, last_data, threshold)

        return False

    def _check_fed_rate_change(self, new_data: Dict, last_data: Dict, threshold: float) -> bool:
        """Check Fed rate change > threshold (default 0.25 = 25BP)."""
        if threshold is None:
            threshold = 0.25

        new_rate = new_data.get("us", {}).get("fed_funds_rate")
        last_rate = last_data.get("us", {}).get("fed_funds_rate")

        if new_rate is None or last_rate is None:
            return False

        change = abs(new_rate - last_rate)
        if change > threshold:
            logger.info(f"[EventTriggerDetector] Fed rate change {change:.2%} > threshold {threshold:.2%}")
            return True

        return False

    def _check_china_rate_change(self, new_data: Dict, last_data: Dict, threshold: float) -> bool:
        """Check China RRR/MLF rate change > threshold."""
        if threshold is None:
            threshold = 0.1

        new_mlf = new_data.get("china", {}).get("mlf_rate")
        last_mlf = last_data.get("china", {}).get("mlf_rate")

        if new_mlf and last_mlf and abs(new_mlf - last_mlf) > threshold:
            return True

        # Also check DR007 as proxy
        new_dr007 = new_data.get("china", {}).get("dr007")
        last_dr007 = last_data.get("china", {}).get("dr007")

        if new_dr007 and last_dr007 and abs(new_dr007 - last_dr007) > threshold:
            return True

        return False

    def _check_tariff_change(self, new_data: Dict, last_data: Dict) -> bool:
        """Check tariff policy major change."""
        new_tariff = new_data.get("global", {}).get("tariff_risk", "normal")
        last_tariff = last_data.get("global", {}).get("tariff_risk", "normal")

        # Any change from normal to elevated/severe triggers
        if new_tariff != last_tariff and new_tariff in ["elevated", "severe"]:
            return True

        return False

    def _check_geopolitical_change(self, new_data: Dict, last_data: Dict) -> bool:
        """Check geopolitical conflict escalation."""
        new_risk = new_data.get("global", {}).get("geopolitical_risk", "normal")
        last_risk = last_data.get("global", {}).get("geopolitical_risk", "normal")

        if new_risk != last_risk and new_risk in ["elevated", "severe"]:
            return True

        return False

    def _check_polymarket_change(self, new_data: Dict, last_data: Dict, threshold: float) -> bool:
        """Check Polymarket probability change > threshold (default 0.2 = 20%)."""
        if threshold is None:
            threshold = 0.2

        new_poly = new_data.get("global", {}).get("polymarket", {})
        last_poly = last_data.get("global", {}).get("polymarket", {})

        for market_id, new_prob in new_poly.items():
            last_prob = last_poly.get(market_id, new_prob)
            if isinstance(new_prob, dict):
                new_prob = new_prob.get("probability", 0.5)
            if isinstance(last_prob, dict):
                last_prob = last_prob.get("probability", 0.5)

            change = abs(float(new_prob) - float(last_prob))
            if change > threshold:
                logger.info(f"[EventTriggerDetector] Polymarket {market_id} change {change:.2%} > threshold {threshold:.2%}")
                return True

        return False

    def _check_pmi_surprise(self, new_data: Dict, last_data: Dict, threshold: float) -> bool:
        """Check PMI surprise > threshold (default 2.0 points)."""
        if threshold is None:
            threshold = 2.0

        # PMI surprise = actual vs expected (simplified: use MoM change as proxy)
        new_pmi = new_data.get("china", {}).get("pmi")
        last_pmi = last_data.get("china", {}).get("pmi")

        if new_pmi and last_pmi:
            mom_change = abs(new_pmi - last_pmi)
            if mom_change > threshold:
                return True

        return False

    def _check_nonfarm_surprise(self, new_data: Dict, last_data: Dict, threshold: float) -> bool:
        """Check Nonfarm surprise > threshold (default 100k)."""
        if threshold is None:
            threshold = 100000

        new_nonfarm = new_data.get("us", {}).get("nonfarm_payrolls")
        last_nonfarm = last_data.get("us", {}).get("nonfarm_payrolls")

        if new_nonfarm and last_nonfarm:
            surprise = abs(new_nonfarm - last_nonfarm)
            if surprise > threshold:
                return True

        return False
