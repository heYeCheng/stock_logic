# -*- coding: utf-8 -*-
"""
AnalysisEngine: orchestrates the full three-layer analysis pipeline.

Provides:
  run(date):          run analysis for a given date
  replay(date):       replay analysis on historical data (no collection)
  compare(dates):     compare analysis results across multiple dates

Dependencies:
  - DataStore: data access
  - SkillLoader: configuration loading
  - LLM Client: AI calls (optional)
  - EventBus: event publishing (optional)
"""

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.sector_logic.datastore import DataStore
from src.sector_logic.skill_loader import SectorLogicSkillLoader
from src.sector_logic.framework_cache import FrameworkCache
from src.sector_logic.agents.sector_agent import SectorAgent
from src.sector_logic.services.event_bus import EventBus
from src.sector_logic.services.metrics import SectorLogicMetrics

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """
    Orchestrates three-layer analysis: Macro → Sector → Stock → Composite.

    Pure computation: only reads from DataStore, never writes snapshots.
    """

    def __init__(
        self,
        datastore: Optional[DataStore] = None,
        skill_loader: Optional[SectorLogicSkillLoader] = None,
        framework_cache: Optional[FrameworkCache] = None,
        llm_client=None,
        event_bus: Optional[EventBus] = None,
        metrics: Optional[SectorLogicMetrics] = None,
    ):
        self.datastore = datastore or DataStore()
        self.skill_loader = skill_loader or SectorLogicSkillLoader()
        self.framework_cache = framework_cache or FrameworkCache(
            skill_loader=self.skill_loader
        )
        self.llm_client = llm_client
        self.event_bus = event_bus or EventBus()
        self.metrics = metrics or SectorLogicMetrics()

        # Initialize agents and services
        self.sector_agent = SectorAgent(
            llm_client=self.llm_client,
            skill_loader=self.skill_loader,
            datastore=self.datastore,
        )

        # Lazy-initialized stock/composite services
        self._stock_radar_scorer = None
        self._buffett_filter = None
        self._decision_matrix = None
        self._composite_selector = None
        self._operation_suggester = None

        # Phase 0.5: L0 + L1 services (lazy-initialized)
        self._macro_analyzer = None
        self._logic_engine = None
        self._event_scoreboard = None
        self._anchor_loader = None
        self._macro_event_repo = None
        self._event_repo = None
        self._logic_repo = None

        # Phase 0.5b: L2 + L3 + L4 services (lazy-initialized)
        self._market_layer = None
        self._stock_mapper = None
        self._stock_scorer = None
        self._execution_layer = None

    def _get_stock_radar_scorer(self):
        if self._stock_radar_scorer is None:
            from src.sector_logic.services.stock_radar_scorer import StockRadarScorer
            self._stock_radar_scorer = StockRadarScorer(self.skill_loader)
        return self._stock_radar_scorer

    def _get_buffett_filter(self):
        if self._buffett_filter is None:
            from src.sector_logic.services.buffett_filter import BuffettFilter
            self._buffett_filter = BuffettFilter(self.skill_loader, self.llm_client)
        return self._buffett_filter

    def _get_decision_matrix(self):
        if self._decision_matrix is None:
            from src.sector_logic.services.decision_matrix import DecisionMatrix
            self._decision_matrix = DecisionMatrix(self.skill_loader)
        return self._decision_matrix

    def _get_composite_selector(self):
        if self._composite_selector is None:
            from src.sector_logic.services.composite_selector import CompositeSelector
            self._composite_selector = CompositeSelector(self.skill_loader)
        return self._composite_selector

    def _get_operation_suggester(self):
        if self._operation_suggester is None:
            from src.sector_logic.services.operation_suggester import OperationSuggester
            self._operation_suggester = OperationSuggester(self.skill_loader)
        return self._operation_suggester

    # =========================================================================
    # Phase 0.5: L0 + L1 services (lazy-initialized)
    # =========================================================================

    def _get_anchor_loader(self):
        if self._anchor_loader is None:
            from src.sector_logic.anchor_loader import AnchorLoader
            self._anchor_loader = AnchorLoader()
        return self._anchor_loader

    def _get_macro_event_repo(self):
        if self._macro_event_repo is None:
            # Initialize tables first
            from src.sector_logic.db_schema import init_tables
            from src.storage import engine
            init_tables(engine)
            from src.sector_logic.repositories.macro_event_repo import MacroEventRepo
            self._macro_event_repo = MacroEventRepo()
        return self._macro_event_repo

    def _get_event_repo(self):
        if self._event_repo is None:
            from src.sector_logic.db_schema import init_tables
            from src.storage import engine
            init_tables(engine)
            from src.sector_logic.repositories.event_repo import EventRepo
            self._event_repo = EventRepo()
        return self._event_repo

    def _get_logic_repo(self):
        if self._logic_repo is None:
            from src.sector_logic.db_schema import init_tables
            from src.storage import engine
            init_tables(engine)
            from src.sector_logic.repositories.logic_repo import LogicRepo
            self._logic_repo = LogicRepo()
        return self._logic_repo

    def _get_macro_analyzer(self):
        if self._macro_analyzer is None:
            from src.sector_logic.services.macro_environment_analyzer import MacroEnvironmentAnalyzer
            self._macro_analyzer = MacroEnvironmentAnalyzer(
                anchor_loader=self._get_anchor_loader(),
                macro_event_repo=self._get_macro_event_repo(),
            )
        return self._macro_analyzer

    def _get_logic_engine(self):
        if self._logic_engine is None:
            from src.sector_logic.services.logic_engine import LogicEngine
            self._logic_engine = LogicEngine(
                llm_client=self.llm_client,
                anchor_loader=self._get_anchor_loader(),
                logic_repo=self._get_logic_repo(),
            )
        return self._logic_engine

    def _get_event_scoreboard(self):
        if self._event_scoreboard is None:
            from src.sector_logic.services.event_scoreboard import EventScoreboard
            self._event_scoreboard = EventScoreboard(
                event_repo=self._get_event_repo(),
                logic_repo=self._get_logic_repo(),
                anchor_loader=self._get_anchor_loader(),
                llm_client=self.llm_client,
            )
        return self._event_scoreboard

    # Phase 0.5b: L2, L3, L4 services
    def _get_market_layer(self):
        if self._market_layer is None:
            from src.sector_logic.services.market_layer import MarketLayer
            self._market_layer = MarketLayer(
                anchor_loader=self._get_anchor_loader(),
            )
        return self._market_layer

    def _get_stock_mapper(self):
        if self._stock_mapper is None:
            from src.sector_logic.services.stock_mapper import StockMapper
            self._stock_mapper = StockMapper(
                anchor_loader=self._get_anchor_loader(),
                tushare_fetcher=None,  # TODO: inject Tushare fetcher
                llm_client=self.llm_client,
            )
        return self._stock_mapper

    def _get_stock_scorer(self):
        if self._stock_scorer is None:
            from src.sector_logic.services.stock_scorer import StockScorer
            self._stock_scorer = StockScorer(
                stock_mapper=self._get_stock_mapper(),
                anchor_loader=self._get_anchor_loader(),
            )
        return self._stock_scorer

    def _get_execution_layer(self):
        if self._execution_layer is None:
            from src.sector_logic.services.execution_layer import ExecutionLayer
            self._execution_layer = ExecutionLayer(
                anchor_loader=self._get_anchor_loader(),
            )
        return self._execution_layer

    async def run_phase05_pipeline(self, sectors: List[str] = None,
                                   stock_pool: List[str] = None) -> Dict[str, Any]:
        """
        Run Phase 0.5 full L0 → L1 → L2 → L3 → L4 pipeline.

        Args:
            sectors: List of sector codes to analyze. If None, uses all active sectors.
            stock_pool: List of stock codes to score. If None, skips stock scoring.

        Returns:
            {
                "macro": {multiplier, quadrant, status, ...},
                "sectors": {sector_code: {logics: [...], strengths: {...}, market: {...}, structure: {...}}},
                "stocks": {stock_code: {logic_score, market_score, composite, catalyst, status}},
                "recommendations": [{rank, code, name, composite_score, position, tag}],
            }
        """
        start_time = time.time()
        logger.info("[Phase05] Starting L0 → L4 pipeline")

        # Step 1: L0 — Calculate macro multiplier
        try:
            macro_analyzer = self._get_macro_analyzer()
            macro_result = macro_analyzer.calculate_multiplier()
            logger.info(f"[Phase05] L0: macro_multiplier={macro_result['multiplier']}, "
                        f"quadrant={macro_result['quadrant']}")
        except Exception as e:
            logger.error(f"[Phase05] L0 failed: {e}")
            macro_result = {
                'multiplier': 1.00,
                'quadrant': '中性',
                'status': 'MACRO_DATA_UNAVAILABLE',
                'alignment_status': '计算失败',
                'event_adjustment': 0.0,
                'updated_at': date.today().isoformat(),
            }

        # Step 2: L1 — For each sector, identify/update logics
        sector_results = {}
        logic_engine = self._get_logic_engine()
        event_scoreboard = self._get_event_scoreboard()

        for sector_code in (sectors or []):
            try:
                logger.info(f"[Phase05] L1: processing sector {sector_code}")

                existing_logics = logic_engine.get_active_logics(sector_code)

                if not existing_logics:
                    sector_name = sector_code
                    sector_description = ""
                    logics = await logic_engine.identify_logics(
                        sector_code=sector_code,
                        sector_name=sector_name,
                        sector_description=sector_description,
                    )
                else:
                    logics = existing_logics

                strengths = {}
                for logic in logics:
                    logic_id = logic.get('logic_id', logic.get('id')) if isinstance(logic, dict) else logic.logic_id
                    strength = event_scoreboard.calculate_strength(logic_id)
                    strengths[logic_id] = strength

                sector_results[sector_code] = {
                    'logics': logics,
                    'strengths': strengths,
                    'market': {},
                    'structure': {},
                    'stocks': {},
                }

            except Exception as e:
                logger.error(f"[Phase05] L1 failed for {sector_code}: {e}")
                sector_results[sector_code] = {
                    'logics': [],
                    'strengths': {},
                    'market': {},
                    'structure': {},
                    'stocks': {},
                    'error': str(e),
                }

        # Step 3: L2 — Market radar for each sector
        market_layer = self._get_market_layer()
        for sector_code, sector_data in sector_results.items():
            if sector_data.get('error'):
                continue

            try:
                # Market radar calculation (requires real data, using mock for now)
                # In production, this would fetch real sector stock data
                market_radar = market_layer.calculate_technical_score([])
                sentiment_result = market_layer.calculate_sentiment_score({}, [], 0)
                strength = market_layer.calculate_composite_strength(
                    market_radar['technical'], sentiment_result['sentiment']
                )
                state = market_layer.classify_state(strength, sentiment_result['sentiment'])
                concentration = market_layer.calculate_concentration([])

                sector_data['market'] = {
                    **market_radar,
                    **sentiment_result,
                    'composite_strength': strength,
                    'state': state,
                }
                sector_data['structure'] = concentration

            except Exception as e:
                logger.error(f"[Phase05] L2 failed for {sector_code}: {e}")
                sector_data['market'] = {'error': str(e)}

        # Step 4: L3 — Stock scoring
        stock_results = {}
        if stock_pool:
            stock_mapper = self._get_stock_mapper()
            stock_scorer = self._get_stock_scorer()

            for stock_code in stock_pool:
                try:
                    # Calculate logic score
                    # Find which sectors this stock belongs to
                    affiliations = stock_mapper.build_affiliations(stock_code)
                    active_logics = []
                    for aff in affiliations:
                        sector_code = aff['sector_code']
                        if sector_code in sector_results:
                            for logic in sector_results[sector_code].get('logics', []):
                                if logic.get('is_active', True):
                                    active_logics.append(logic)

                    logic_score = stock_scorer.calculate_logic_score(
                        stock_code, affiliations[0]['sector_code'] if affiliations else '',
                        active_logics
                    )
                    market_score = stock_scorer.calculate_market_score({})
                    composite = stock_scorer.calculate_composite(logic_score, market_score)
                    catalyst = stock_scorer.calculate_catalyst({})
                    status = stock_scorer.identify_stock_status({
                        'logic_match_score': stock_mapper.get_logic_match_score(
                            stock_code, affiliations[0]['sector_code'] if affiliations else ''
                        ),
                        'stock_market_score': market_score,
                    })

                    stock_results[stock_code] = {
                        'logic_score': logic_score,
                        'market_score': market_score,
                        'composite': composite,
                        'catalyst': catalyst,
                        'status': status,
                        'affiliations': affiliations,
                    }

                except Exception as e:
                    logger.error(f"[Phase05] L3 failed for {stock_code}: {e}")

        # Step 5: L4 — Execution & recommendations
        execution_layer = self._get_execution_layer()
        recommendations = []

        for stock_code, stock_data in stock_results.items():
            try:
                # Calculate net thrust from sector logics
                net_thrust = 0.0
                has_headwind = False
                sector_structure = ''
                market_state = 'normal'

                for aff in stock_data.get('affiliations', []):
                    sector_code = aff['sector_code']
                    if sector_code in sector_results:
                        strengths = sector_results[sector_code].get('strengths', {})
                        if strengths:
                            pos_force = sum(v for k, v in strengths.items() if k.startswith('pos'))
                            neg_force = sum(v for k, v in strengths.items() if k.startswith('neg'))
                            net_thrust = pos_force - neg_force
                            has_headwind = neg_force > 0.4
                        sector_structure = sector_results[sector_code].get('structure', {}).get('structure_type', '')
                        market_state = sector_results[sector_code].get('market', {}).get('state', {}).get('state', 'normal')

                position_result = execution_layer.calculate_position(
                    net_thrust=net_thrust,
                    stock_composite_score=stock_data['composite'],
                    market_strength_score=stock_data['market_score'],
                    macro_multiplier=macro_result.get('multiplier', 1.0),
                    has_headwind=has_headwind,
                    sector_structure_type=sector_structure,
                )

                constraints = execution_layer.check_trading_constraints(stock_code, {})

                if not constraints.get('can_buy', True):
                    continue  # Skip non-buyable stocks

                logic_match = stock_data.get('logic_match_score', 0.1)
                tag = execution_layer.generate_recommendation_tag(
                    logic_match, stock_data['market_score']
                )

                recommendations.append({
                    'code': stock_code,
                    'composite_score': round(stock_data['composite'] * 100, 0),
                    'position': position_result['position'],
                    'position_score': position_result['position_score'],
                    'tag': tag,
                    'warning': constraints.get('warning'),
                })

            except Exception as e:
                logger.error(f"[Phase05] L4 failed for {stock_code}: {e}")

        # Sort recommendations by composite score
        recommendations.sort(key=lambda x: x['composite_score'], reverse=True)
        recommendations = recommendations[:20]  # Top 20

        # Add rank
        for i, rec in enumerate(recommendations):
            rec['rank'] = i + 1

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[Phase05] Full pipeline complete in {duration_ms:.0f}ms, "
                     f"generated {len(recommendations)} recommendations")

        return {
            'macro': macro_result,
            'sectors': sector_results,
            'stocks': stock_results,
            'recommendations': recommendations,
            'duration_ms': round(duration_ms, 2),
        }

    async def run(self, d: date) -> Dict[str, Any]:
        """
        Run full analysis for date d.

        Reads collected data from DataStore, runs SectorAgent for each sector,
        computes stock recommendations, returns results dict.

        Returns:
            {
                "date": "...",
                "macro_context": {...},
                "sector_results": {sector: result, ...},
                "stock_recommendations": {code: radar, ...},
                "issue_queue": [...],
                "flip_events": [...],
            }
        """
        start_time = time.time()
        logger.info(f"[AnalysisEngine] running analysis for {d.isoformat()}")

        # 1. Load macro context
        macro_context = self.datastore.get_snapshot(d, "macro")
        if macro_context is None:
            macro_context = {
                "macro_thesis_score": 0.5,
                "macro_state": "neutral",
                "summary": "macro data not available",
            }

        # 2. Load all sector collected data
        sector_data = self._load_all_sector_data(d)

        # 3. Run SectorAgent for each sector (async)
        import asyncio
        sector_results = {}
        all_flip_events = []
        all_issues = []

        tasks = []
        for sector, data in sector_data.items():
            tasks.append(self._run_sector_analysis(sector, d, data or {}, macro_context))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for sector, result in zip(sector_data.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"[AnalysisEngine] sector analysis error for {sector}: {result}")
                    sector_results[sector] = {}
                else:
                    sector_results[sector] = result
                    all_flip_events.extend(result.get("flip_events", []))
                    all_issues.extend(result.get("issue_queue", []))

                    sl = result.get("sector_logic", {})
                    self.metrics.record_sector_analysis(
                        sector=sector,
                        logic_category=sl.get("sector_dominant_logic_category", "unknown"),
                        strength=sl.get("sector_logic_strength", 0.5),
                        duration_ms=0,  # Placeholder
                    )

        # 4. Compute stock recommendations
        stock_recommendations = await self._compute_stock_recommendations(
            d, sector_results
        )

        # 5. Publish flip events
        for flip_event in all_flip_events:
            await self.event_bus.publish_flip_event(flip_event)
            self.metrics.record_flip_event(flip_event.get("flip_type", "unknown"))

        # 6. Publish analysis complete event
        await self.event_bus.publish_analysis_complete({
            "date": d.isoformat(),
            "sector_count": len(sector_results),
            "stock_count": len(stock_recommendations) if isinstance(stock_recommendations, dict) else 0,
            "flip_event_count": len(all_flip_events),
            "issue_count": len(all_issues),
        })

        duration_ms = (time.time() - start_time) * 1000
        self.metrics.record_analysis_duration(d.isoformat(), duration_ms)

        return {
            "date": d.isoformat(),
            "macro_context": macro_context,
            "sector_results": sector_results,
            "stock_recommendations": stock_recommendations,
            "issue_queue": all_issues,
            "flip_events": all_flip_events,
            "metrics": self.metrics.summary(),
            "duration_ms": round(duration_ms, 2),
        }

    async def _run_sector_analysis(
        self,
        sector: str,
        d: date,
        collected_data: Dict[str, Any],
        macro_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run SectorAgent for one sector."""
        return await self.sector_agent.analyze_sector(
            sector=sector,
            d=d,
            collected_data=collected_data,
            macro_context=macro_context,
        )

    async def _compute_stock_recommendations(
        self,
        d: date,
        sector_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute stock recommendations based on sector results.

        Loads stock collected data, applies sector logic scores,
        runs radar scoring, Buffett filter, decision matrix, and composite selection.
        """
        stocks_dir = self.datastore.snapshots_dir / d.isoformat() / "stocks"
        if not stocks_dir.exists():
            logger.warning(f"[AnalysisEngine] no stock data for {d.isoformat()}")
            return {}

        # Build sector result lookup
        sector_logic_lookup = {}
        for sector, result in sector_results.items():
            sl = result.get("sector_logic", {})
            sector_logic_lookup[sector] = sl

        stock_radar_scorer = self._get_stock_radar_scorer()
        buffett_filter = self._get_buffett_filter()
        decision_matrix = self._get_decision_matrix()

        stock_results = []
        for stock_file in stocks_dir.glob("*.json"):
            code = stock_file.stem
            with open(stock_file, "r", encoding="utf-8") as f:
                stock_data = json.load(f)

            sector_name = stock_data.get("sector", "")
            sector_result = sector_logic_lookup.get(sector_name, {})

            try:
                # Radar scoring
                radar_result = await stock_radar_scorer.score(
                    stock_code=code,
                    stock_data=stock_data,
                    sector_result=sector_result,
                    d=d,
                )

                # Buffett filter
                qual_data = stock_data.get("qualitative_data", {})
                buffett_result = await buffett_filter.filter(code, qual_data)

                # Decision matrix
                tier_result = decision_matrix.classify(
                    stock_code=code,
                    stock_thesis_score=radar_result["stock_thesis_score"],
                    buffett_result=buffett_result["final_result"],
                    stock_metadata=stock_data.get("metadata"),
                )

                stock_results.append({
                    **radar_result,
                    **buffett_result,
                    **tier_result,
                    "sector": sector_name,
                })
            except Exception as e:
                logger.error(f"[AnalysisEngine] stock analysis failed for {code}: {e}")

        # Composite selection
        if stock_results:
            composite_selector = self._get_composite_selector()
            composite_result = composite_selector.select(
                macro_result={"macro_thesis_score": 0.5},  # Simplified
                sector_results={k: v for k, v in sector_logic_lookup.items()},
                stock_results=stock_results,
            )

            # Generate suggestions
            operation_suggester = self._get_operation_suggester()
            suggestions = operation_suggester.generate(composite_result["tiers"])

            return {
                "stocks": stock_results,
                "composite": composite_result,
                "suggestions": suggestions,
            }

        return {}

    def replay(self, d: date) -> Dict[str, Any]:
        """
        Replay analysis on historical date d.
        Same as run() but explicitly labeled as replay.
        Does NOT trigger any data collection.
        """
        logger.info(f"[AnalysisEngine] replaying analysis for {d.isoformat()}")
        return self.run(d)

    def compare(self, dates: List[date]) -> Dict[str, Any]:
        """
        Compare analysis results across multiple dates.
        """
        logger.info(f"[AnalysisEngine] comparing dates: {[d.isoformat() for d in dates]}")

        import asyncio

        async def _compare():
            results = {}
            for d in dates:
                results[d.isoformat()] = await self.run(d)

            comparison = {
                "dates": [d.isoformat() for d in dates],
                "macro_comparison": [
                    results.get(d.isoformat(), {}).get("macro_context")
                    for d in dates
                ],
                "sector_comparison": {},
                "stock_comparison": {},
                "flip_events": [],
            }

            all_sectors = set()
            for d in dates:
                sr = results.get(d.isoformat(), {}).get("sector_results", {})
                all_sectors.update(sr.keys())

            for sector in all_sectors:
                comparison["sector_comparison"][sector] = [
                    results.get(d.isoformat(), {}).get("sector_results", {}).get(sector)
                    for d in dates
                ]

            return comparison

        return asyncio.get_event_loop().run_until_complete(_compare())

    def _load_all_sector_data(self, d: date) -> Dict[str, Optional[Dict[str, Any]]]:
        """Load all sector collected data from DataStore."""
        sectors_dir = self.datastore.snapshots_dir / d.isoformat() / "sectors"
        if not sectors_dir.exists():
            logger.warning(f"[AnalysisEngine] no sector data for {d.isoformat()}")
            return {}

        sector_data = {}
        for sector_file in sectors_dir.glob("*.json"):
            sector_name = sector_file.stem
            with open(sector_file, "r", encoding="utf-8") as f:
                sector_data[sector_name] = json.load(f)

        return sector_data
