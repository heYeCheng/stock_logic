# -*- coding: utf-8 -*-
"""
FlipDetector: detects logic flip events.

Flip triggers:
  1. dominant logic_strength < 0.3 (logic collapse)
  2. new logic logic_strength > dominant * 0.8 (new logic approaching)
  3. price behavior diverges from dominant logic for 3+ consecutive days

Output: LogicFlipEvent records with:
  - flip_type (dominant_change / dominant_collapse / new_emergence)
  - confidence
  - mode (left_side / right_side)
  - trigger_signals
  - action_hint
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlipDetector:
    """
    Detects when dominant logic is being replaced.

    Uses threshold-based detection:
      - FLIP_THRESHOLD_1: dominant logic_strength < 0.3
      - FLIP_THRESHOLD_2: new logic_strength > dominant * 0.8
      - PRICE_DIVERGENCE_DAYS: 3 consecutive days of price-logic divergence
    """

    FLIP_THRESHOLD_1 = 0.3
    FLIP_THRESHOLD_2 = 0.8
    PRICE_DIVERGENCE_DAYS = 3

    def __init__(self):
        self._previous_dominant = {}  # sector_id -> previous dominant logic info

    def check(
        self,
        sector: str,
        logics: List[Dict[str, Any]],
        d: date,
        price_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a flip event should be triggered.

        Args:
            sector: sector name
            logics: list of TradingLogic dicts for this sector
            d: analysis date
            price_data: optional price behavior data

        Returns:
            LogicFlipEvent dict if flip detected, None otherwise
        """
        if not logics:
            return None

        sorted_logics = sorted(
            logics, key=lambda l: l.get("logic_strength", 0), reverse=True
        )

        current_dominant = sorted_logics[0]
        prev_info = self._previous_dominant.get(sector)

        # Check flip conditions
        flip_type = self._detect_flip(current_dominant, sorted_logics, prev_info)

        if not flip_type:
            # Update previous dominant
            self._previous_dominant[sector] = {
                "logic_id": current_dominant.get("logic_id"),
                "logic_strength": current_dominant.get("logic_strength", 0.5),
                "date": d.isoformat(),
            }
            return None

        # Build flip event
        new_dominant = sorted_logics[0] if flip_type != "dominant_collapse" else None

        confidence = self._calc_confidence(
            flip_type, current_dominant, sorted_logics
        )

        mode = self._determine_mode(flip_type, current_dominant, prev_info)

        event = {
            "sector": sector,
            "flip_type": flip_type,
            "old_dominant_logic_id": current_dominant.get("logic_id") if prev_info and prev_info.get("logic_id") != current_dominant.get("logic_id") else (prev_info.get("logic_id") if prev_info else None),
            "new_dominant_logic_id": new_dominant.get("logic_id") if new_dominant else None,
            "confidence": confidence,
            "mode": mode,
            "trigger_signals": self._get_trigger_signals(flip_type, current_dominant, sorted_logics),
            "detected_at": d.isoformat(),
            "action_hint": self._get_action_hint(flip_type, confidence, mode, new_dominant),
        }

        # Update previous dominant
        if new_dominant:
            self._previous_dominant[sector] = {
                "logic_id": new_dominant.get("logic_id"),
                "logic_strength": new_dominant.get("logic_strength", 0.5),
                "date": d.isoformat(),
            }

        logger.info(
            f"[FlipDetector] flip detected for {sector}: {flip_type}, "
            f"confidence={confidence:.2f}, mode={mode}"
        )

        return event

    def _detect_flip(
        self,
        dominant: Dict[str, Any],
        sorted_logics: List[Dict[str, Any]],
        prev_info: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Determine flip type if any threshold is breached.

        Returns: flip_type string or None
        """
        dom_strength = dominant.get("logic_strength", 0.5)
        dom_id = dominant.get("logic_id")

        # Condition 1: dominant collapse
        if dom_strength < self.FLIP_THRESHOLD_1:
            return "dominant_collapse"

        # Condition 2: new logic approaching
        if len(sorted_logics) > 1:
            second = sorted_logics[1]
            second_strength = second.get("logic_strength", 0)
            if second_strength > dom_strength * self.FLIP_THRESHOLD_2:
                # Check if this is a new logic (different from previous dominant)
                if prev_info and prev_info.get("logic_id") != dom_id:
                    return "dominant_change"
                elif second_strength > dom_strength:
                    return "new_emergence"

        # Condition 3: price divergence (TODO: implement with actual price data)
        # if price_data and self._check_price_divergence(price_data):
        #     return "dominant_change"

        return None

    def _calc_confidence(
        self,
        flip_type: str,
        dominant: Dict[str, Any],
        sorted_logics: List[Dict[str, Any]],
    ) -> float:
        """Calculate flip confidence based on trigger conditions."""
        base = 0.5

        if flip_type == "dominant_collapse":
            dom_s = dominant.get("logic_strength", 0.5)
            base = max(0.3, 1.0 - dom_s)
        elif flip_type == "dominant_change":
            if len(sorted_logics) > 1:
                gap = sorted_logics[0].get("logic_strength", 0.5) - sorted_logics[1].get("logic_strength", 0.5)
                base = max(0.4, 0.8 - abs(gap))
        elif flip_type == "new_emergence":
            base = 0.6

        return round(min(base, 0.95), 2)

    def _determine_mode(
        self,
        flip_type: str,
        dominant: Dict[str, Any],
        prev_info: Optional[Dict[str, Any]],
    ) -> str:
        """
        Determine flip mode: left_side (signal confirming) or right_side (trend confirmed).
        """
        dom_trend = dominant.get("logic_strength_trend", "stable")

        if flip_type == "dominant_collapse":
            # Collapse is usually right_side (already happened)
            return "right_side"
        elif flip_type == "new_emergence":
            # New emergence is left_side (early signal)
            return "left_side"
        elif flip_type == "dominant_change":
            if dom_trend == "declining":
                return "right_side"
            return "left_side"

        return "right_side"

    def _get_trigger_signals(
        self,
        flip_type: str,
        dominant: Dict[str, Any],
        sorted_logics: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate trigger signal descriptions."""
        signals = []

        if flip_type == "dominant_collapse":
            signals.append(
                f"主导逻辑强度降至 {dominant.get('logic_strength', 0):.2f}，低于阈值 {self.FLIP_THRESHOLD_1}"
            )
            signals.append(f"逻辑趋势: {dominant.get('logic_strength_trend', 'stable')}")
        elif flip_type == "dominant_change" and len(sorted_logics) > 1:
            signals.append(
                f"次要逻辑强度 {sorted_logics[1].get('logic_strength', 0):.2f} "
                f"接近主导逻辑 {dominant.get('logic_strength', 0):.2f}"
            )
        elif flip_type == "new_emergence" and len(sorted_logics) > 1:
            signals.append(f"新逻辑出现，强度 {sorted_logics[1].get('logic_strength', 0):.2f}")

        return signals

    def _get_action_hint(
        self,
        flip_type: str,
        confidence: float,
        mode: str,
        new_dominant: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate operation suggestion for the flip event."""
        if flip_type == "dominant_collapse":
            return {
                "mode": mode,
                "certainty": "high" if confidence > 0.7 else "medium",
                "suggestion": "主导逻辑瓦解，建议减仓或离场，等待新逻辑确认",
                "invalidation": "若原逻辑强度快速恢复，可重新评估",
            }
        elif flip_type == "dominant_change":
            return {
                "mode": mode,
                "certainty": "medium" if mode == "left_side" else "high",
                "suggestion": f"逻辑切换中，{'观察2-3日确认' if mode == 'left_side' else '新逻辑已确认，可中等仓位试探'}",
                "invalidation": f"若{new_dominant.get('title', '新逻辑')}强度快速下降，应立即退出",
            }
        elif flip_type == "new_emergence":
            return {
                "mode": mode,
                "certainty": "low",
                "suggestion": "新逻辑初现但尚未确认，建议观察，暂不操作",
                "invalidation": "若新逻辑快速证伪，标记为失效",
            }

        return {
            "mode": mode,
            "certainty": "unknown",
            "suggestion": "建议观望",
            "invalidation": "不适用",
        }
