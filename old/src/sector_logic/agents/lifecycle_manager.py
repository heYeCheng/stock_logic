# -*- coding: utf-8 -*-
"""
LifecycleManager: manages TradingLogic lifecycle state transitions.

Input:
  - TradingLogic (from SectorAgent)
  - Logic strength history
  - Skill files: lifecycle/state-machine.json, lifecycle/transition-rules.json

Process:
  1. Load lifecycle state machine and transition rules
  2. Check current state and conditions
  3. Execute state transition if conditions met
  4. Check for flip events (dominant_collapse, new_emergence, price_divergence)

Output:
  - LifecycleState dict
  - Optional LogicFlipEvent (if flip detected)

Lifecycle States (5 stages):
  1. discovery (发现期): Logic刚被识别，strength < 0.4
  2. tracking (追踪期): Logic被确认，strength >= 0.4
  3. monitoring (监控期): Logic稳定，strength >= 0.6
  4. confirmation (确认期): Logic被充分验证，strength >= 0.75
  5. output (输出期): Logic已兑现或瓦解
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Manages TradingLogic lifecycle state transitions.
    """

    # Lifecycle state names
    STATES = ["discovery", "tracking", "monitoring", "confirmation", "output"]

    def __init__(self, skill_loader, datastore=None):
        self.skill_loader = skill_loader
        self.datastore = datastore
        self._state_machine = None
        self._transition_rules = None

    def _load_state_machine(self) -> Dict[str, Any]:
        """Load lifecycle state machine from skill file."""
        if self._state_machine:
            return self._state_machine

        # Try loading via skill_loader
        state_machine = self.skill_loader._load_json_model("lifecycle/state-machine.json")
        if state_machine:
            self._state_machine = state_machine
        else:
            # Fallback: load directly
            skill_dir = self.skill_loader.skill_dir
            path = skill_dir / "lifecycle" / "state-machine.json"
            if path.exists():
                self._state_machine = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._state_machine = {"states": []}

        return self._state_machine

    def _load_transition_rules(self) -> Dict[str, Any]:
        """Load transition rules from skill file."""
        if self._transition_rules:
            return self._transition_rules

        rules = self.skill_loader._load_json_model("lifecycle/transition-rules.json")
        if rules:
            self._transition_rules = rules
        else:
            # Fallback: load directly
            skill_dir = self.skill_loader.skill_dir
            path = skill_dir / "lifecycle" / "transition-rules.json"
            if path.exists():
                self._transition_rules = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._transition_rules = {"thresholds": {}}

        return self._transition_rules

    async def transition(
        self,
        logic: Dict[str, Any],
        strength: float,
        issues: List[Dict],
        d: date,
        other_logics: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Execute lifecycle state transition.

        Args:
            logic: TradingLogic dict
            strength: Current logic strength (0-1)
            issues: Issue queue entries
            d: Analysis date
            other_logics: Other logics in the same sector (for flip detection)

        Returns:
            LifecycleState dict with:
            - status (emerging/dominant/secondary/fading)
            - stage (discovery/tracking/monitoring/confirmation/output)
            - strength_history
            - strength_trend
            - last_transition
        """
        logger.info(f"[LifecycleManager] transitioning {logic.get('sector')} logic")

        # Load configs
        state_machine = self._load_state_machine()
        rules = self._load_transition_rules()

        # Load or initialize state
        state = await self._load_state(logic.get("logic_id"), d)

        # Update strength history
        state = self._update_strength_history(state, strength)

        # Calculate strength trend
        state["strength_trend"] = self._calc_trend(state.get("strength_history", []))

        # Check state transitions
        state = self._check_transitions(state, logic, strength, issues, rules)

        # Save state
        await self._save_state(logic.get("logic_id"), state, d)

        logger.info(f"[LifecycleManager] {logic.get('sector')} state={state['stage']}, status={state['status']}")
        return state

    async def _load_state(self, logic_id: str, d: date) -> Dict[str, Any]:
        """Load lifecycle state from datastore or initialize new."""
        if self.datastore:
            cached = self.datastore.get_lifecycle_state(logic_id)
            if cached:
                return cached

        # Initialize new state
        return {
            "logic_id": logic_id,
            "status": "emerging",
            "stage": "discovery",
            "strength_history": [],
            "strength_trend": "stable",
            "last_transition": None,
            "last_updated": d.isoformat(),
        }

    async def _save_state(self, logic_id: str, state: Dict[str, Any], d: date) -> None:
        """Save lifecycle state to datastore."""
        state["last_updated"] = d.isoformat()

        if self.datastore:
            self.datastore.save_lifecycle_state(logic_id, state)

    def _update_strength_history(self, state: Dict[str, Any], strength: float) -> Dict[str, Any]:
        """Update strength history (keep last 30 days)."""
        history = state.get("strength_history", [])
        history.append(strength)

        # Keep only last 30 entries
        if len(history) > 30:
            history = history[-30:]

        state["strength_history"] = history
        return state

    def _calc_trend(self, history: List[float]) -> str:
        """Calculate strength trend from history."""
        if len(history) < 5:
            return "stable"

        recent_avg = sum(history[-5:]) / 5
        previous_avg = sum(history[-10:-5]) / 5

        if recent_avg > previous_avg * 1.1:
            return "increasing"
        elif recent_avg < previous_avg * 0.9:
            return "declining"
        else:
            return "stable"

    def _check_transitions(
        self,
        state: Dict[str, Any],
        logic: Dict[str, Any],
        strength: float,
        issues: List[Dict],
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check and execute state transitions."""
        thresholds = rules.get("thresholds", {})
        current_stage = state.get("stage", "discovery")
        current_status = state.get("status", "emerging")

        # discovery → tracking
        if current_stage == "discovery" and strength >= thresholds.get("discovery_to_tracking", {}).get("min_logic_strength", 0.4):
            state["stage"] = "tracking"
            state["last_transition"] = "discovery → tracking"
            logger.info(f"[LifecycleManager] transition: discovery → tracking")

        # tracking → monitoring
        elif current_stage == "tracking" and strength >= thresholds.get("tracking_to_monitoring", {}).get("min_logic_strength", 0.6):
            # Check consecutive days requirement (simplified for MVP)
            state["stage"] = "monitoring"
            state["last_transition"] = "tracking → monitoring"
            logger.info(f"[LifecycleManager] transition: tracking → monitoring")

        # monitoring → confirmation
        elif current_stage == "monitoring" and strength >= thresholds.get("monitoring_to_confirmation", {}).get("min_logic_strength", 0.75):
            state["stage"] = "confirmation"
            state["last_transition"] = "monitoring → confirmation"
            logger.info(f"[LifecycleManager] transition: monitoring → confirmation")

        # Any → output (falsified)
        elif strength <= thresholds.get("any_to_output_falsified", {}).get("max_logic_strength", 0.3):
            state["stage"] = "output"
            state["status"] = "dead"
            state["last_transition"] = f"{current_stage} → output (falsified)"
            logger.info(f"[LifecycleManager] transition: {current_stage} → output (falsified)")

        # Status transitions (dominant/secondary/fading)
        if strength >= 0.5:
            state["status"] = "dominant"
        elif strength >= 0.35:
            state["status"] = "secondary"
        else:
            state["status"] = "fading"

        return state

    async def check_flip(
        self,
        logic: Dict[str, Any],
        state: Dict[str, Any],
        other_logics: List[Dict],
        d: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if logic flip event is triggered.

        Args:
            logic: Current dominant TradingLogic
            state: LifecycleState
            other_logics: Other logics in the same sector
            d: Analysis date

        Returns:
            LogicFlipEvent dict or None
        """
        rules = self._load_transition_rules()
        flip_rules = rules.get("flip_detection", {})

        sector = logic.get("sector", "unknown")
        current_strength = logic.get("logic_strength", 0.5)

        # Trigger 1: Dominant collapse
        trigger_1 = flip_rules.get("trigger_1_dominant_collapse", {})
        if state.get("status") == "dominant" and current_strength < trigger_1.get("condition_value", 0.4):
            return self._build_flip_event(
                logic, state, "dominant_collapse", d,
                confidence=trigger_1.get("confidence_threshold", 0.7)
            )

        # Trigger 2: New emergence
        trigger_2 = flip_rules.get("trigger_2_new_emergence", {})
        for other in other_logics:
            if other.get("logic_id") != logic.get("logic_id"):
                other_strength = other.get("logic_strength", 0)
                threshold = trigger_2.get("condition_value", 0.8)
                if other_strength > current_strength * threshold:
                    return self._build_flip_event(
                        logic, state, "new_emergence", d,
                        confidence=trigger_2.get("confidence_threshold", 0.6),
                        new_logic=other
                    )

        # Trigger 3: Price divergence (simplified)
        trigger_3 = flip_rules.get("trigger_3_price_divergence", {})
        # Would need price data to check divergence

        return None

    def _build_flip_event(
        self,
        logic: Dict[str, Any],
        state: Dict[str, Any],
        flip_type: str,
        d: date,
        confidence: float = 0.6,
        new_logic: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Build LogicFlipEvent dict."""
        event = {
            "event_type": "logic_flip",
            "flip_type": flip_type,
            "sector": logic.get("sector", "unknown"),
            "logic_id": logic.get("logic_id"),
            "old_logic_category": logic.get("category"),
            "old_logic_strength": logic.get("logic_strength", 0.5),
            "new_logic_category": new_logic.get("category") if new_logic else None,
            "new_logic_strength": new_logic.get("logic_strength") if new_logic else None,
            "confidence": confidence,
            "detected_date": d.isoformat(),
            "action_hint": {
                "suggestion": "观察" if confidence < 0.7 else "减仓" if confidence < 0.8 else "离场",
                "reason": f"{flip_type} detected with {confidence:.0%} confidence",
            },
        }

        logger.warning(f"[LifecycleManager] flip event detected: {flip_type} in {logic.get('sector')}")
        return event
