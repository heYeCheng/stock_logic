# -*- coding: utf-8 -*-
"""
SectorAgent: skill-based sector analysis with 4-stage pipeline.

4-stage pipeline:
  Stage 1: Logic extraction — LogicExtractor classifies logic category
  Stage 2: Strength calculation — StrengthEvaluator evaluates framework dimensions
  Stage 3: Risk scanning — RiskScanner checks risk templates
  Stage 4: Output — LifecycleManager manages state transitions + flip detection
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from src.sector_logic.skill_loader import SectorLogicSkillLoader
from src.sector_logic.agents.logic_extractor import LogicExtractor
from src.sector_logic.agents.strength_evaluator import StrengthEvaluator
from src.sector_logic.agents.lifecycle_manager import LifecycleManager

logger = logging.getLogger(__name__)


class SectorAgent:
    """
    Skill-based sector analysis with 4-stage pipeline.

    Input: sector collected data (index OHLCV, capital flow, news)
    Output: TradingLogic records, SectorLogic scoring, issue queue, flip events
    """

    def __init__(self, llm_client=None, skill_loader=None, datastore=None):
        self.llm_client = llm_client
        self.skill_loader = skill_loader or SectorLogicSkillLoader()
        self.datastore = datastore

        # Initialize 4-stage pipeline components
        self.logic_extractor = LogicExtractor(self.skill_loader, self.llm_client)
        self.strength_evaluator = StrengthEvaluator(self.skill_loader, self.llm_client)
        self.lifecycle_manager = LifecycleManager(self.skill_loader, self.datastore)

    async def analyze_sector(
        self,
        sector: str,
        d: date,
        collected_data: Dict[str, Any],
        macro_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the full 4-stage pipeline for one sector."""
        logger.info(f"[SectorAgent] analyzing {sector} for {d.isoformat()}")

        # Stage 1: Logic extraction
        logic = await self.logic_extractor.extract(sector, d, collected_data, macro_context)
        logics = [logic]

        # Stage 2: Strength calculation
        logic = await self.strength_evaluator.evaluate(logic, collected_data, macro_context)

        # Stage 3: Risk scanning (basic for MVP)
        issue_queue = self._stage3_scan_risks(sector, logics, d)

        # Stage 4: Lifecycle management + flip detection
        lifecycle_state = await self.lifecycle_manager.transition(
            logic=logic,
            strength=logic.get("logic_strength", 0.5),
            issues=issue_queue,
            d=d,
        )

        # Check for flip events
        flip_events = []
        flip_event = await self.lifecycle_manager.check_flip(
            logic=logic,
            state=lifecycle_state,
            other_logics=[],  # MVP: no other logics comparison
            d=d,
        )
        if flip_event:
            flip_events.append(flip_event)

        # Assemble output
        sector_logic = self._assemble_sector_output(
            sector, d, logic, lifecycle_state, macro_context, collected_data
        )

        return {
            "logics": logics,
            "sector_logic": sector_logic,
            "issue_queue": issue_queue,
            "flip_events": flip_events,
            "lifecycle_state": lifecycle_state,
        }

    def _stage3_scan_risks(
        self,
        sector: str,
        logics: List[Dict[str, Any]],
        d: date,
    ) -> List[Dict[str, Any]]:
        """
        Stage 3: Scan risks for all active logics.

        Checks:
        - Logic strength < 0.3 → warning
        - Price declining but news positive → divergence
        """
        from src.sector_logic.risk_scanner import RiskScanner

        scanner = RiskScanner(self.skill_loader)
        return scanner.scan(logics, d)

    def _assemble_sector_output(
        self,
        sector: str,
        d: date,
        logic: Dict[str, Any],
        lifecycle_state: Dict[str, Any],
        macro_context: Optional[Dict[str, Any]],
        collected_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assemble sector-level output with lifecycle state."""
        index_data = collected_data.get("sector_index", {})
        capital = collected_data.get("capital_flow", {})
        news = collected_data.get("news_items", [])

        pct_chg = index_data.get("pct_chg", 0)
        net_flow = capital.get("net_flow", 0)

        # Macro adjustment
        macro_adj = 0.0
        if macro_context:
            macro_score = macro_context.get("macro_thesis_score", 0.5)
            macro_adj = (macro_score - 0.5) * 0.3  # -0.15 to +0.15

        # Radar scores
        logic_strength = logic.get("logic_strength", 0.5)
        radar_logic = min(10, max(0, logic_strength * 10))
        radar_technical = min(10, max(0, 5 + pct_chg))
        radar_capital_flow = min(10, max(0, 5 + net_flow / 200))
        radar_sentiment = min(10, max(0, 3 + len(news) * 0.7))

        return {
            "sector": sector,
            "snapshot_date": d.isoformat(),
            "sector_logic_strength": round(logic_strength, 4),
            "sector_dominant_logic_id": logic.get("logic_id"),
            "sector_dominant_logic_title": logic.get("title"),
            "sector_dominant_logic_category": logic.get("category"),
            "sector_lifecycle_stage": lifecycle_state.get("stage", "discovery"),
            "sector_lifecycle_status": lifecycle_state.get("status", "emerging"),
            "sector_strength_trend": lifecycle_state.get("strength_trend", "stable"),
            "radar_logic": round(radar_logic, 1),
            "radar_fundamental": 5.0,
            "radar_technical": round(radar_technical, 1),
            "radar_capital_flow": round(radar_capital_flow, 1),
            "radar_sentiment": round(radar_sentiment, 1),
            "sector_thesis_score": round(logic_strength, 4),
            "sector_price_score": round(min(1.0, max(0, (pct_chg + 5) / 10)), 4),
            "sector_macro_adjustment": round(macro_adj, 4),
            "sector_logic_strength_framework": logic.get("logic_strength_framework", []),
        }