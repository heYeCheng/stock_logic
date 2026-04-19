"""Macro service - orchestrates macro scoring, quadrant analysis, and persistence."""

import logging
from datetime import date
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import MacroSnapshot, MonetaryConditionEnum, CreditConditionEnum, QuadrantEnum
from src.database.connection import async_session_maker
from src.macro.fetcher import MacroFetcher
from src.macro.scorer import MacroScorer
from src.macro.quadrant import QuadrantAnalyzer, Quadrant, MonetaryCondition, CreditCondition

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    """Data quality degradation levels."""
    FULL = "full"  # All data available
    PARTIAL = "partial"  # Some indicators missing, impute from prior
    LIMITED = "limited"  # All indicators missing, use prior + decay
    MINIMAL = "minimal"  # No prior snapshot, multiplier = 1.00


class MacroService:
    """Orchestrate macro scoring, quadrant analysis, and database persistence."""

    # Decay factor for LIMITED degradation (10% decay per month)
    DECAY_FACTOR = 0.9

    # Uncertainty penalty for PARTIAL degradation (5% discount)
    PARTIAL_PENALTY = 0.95

    def __init__(self):
        self.fetcher = MacroFetcher()
        self.scorer = MacroScorer()
        self.analyzer = QuadrantAnalyzer()

    async def compute_snapshot(self, snapshot_date: date) -> MacroSnapshot:
        """
        Compute macro snapshot with graceful degradation.

        Degradation levels:
        1. FULL: All data available → normal scoring
        2. PARTIAL: Some indicators missing → impute from prior month
        3. LIMITED: All indicators missing → use prior + decay
        4. MINIMAL: No prior snapshot → multiplier = 1.00 (neutral)

        Args:
            snapshot_date: Date for the snapshot

        Returns:
            MacroSnapshot persisted to database
        """
        logger.info(f"Computing macro snapshot for {snapshot_date}")

        try:
            # Step 1: Try to fetch all indicators
            indicators = await self.fetcher.fetch_all()

            # Step 2: Determine degradation level
            degradation = self._assess_data_quality(indicators)
            logger.info(f"Data quality assessment: {degradation.value}")

            if degradation == DegradationLevel.FULL:
                snapshot = await self._compute_full_snapshot(snapshot_date, indicators)
            elif degradation == DegradationLevel.PARTIAL:
                snapshot = await self._compute_partial_snapshot(snapshot_date, indicators)
            elif degradation == DegradationLevel.LIMITED:
                snapshot = await self._compute_limited_snapshot(snapshot_date)
            else:  # MINIMAL
                snapshot = await self._compute_minimal_snapshot(snapshot_date)

            # Persist to database
            await self._save_snapshot(snapshot)
            logger.info(f"Macro snapshot persisted: {snapshot}")

            return snapshot

        except Exception as e:
            # CRITICAL: Never crash, always return at least MINIMAL
            logger.error(f"Unexpected error in macro snapshot: {e}", exc_info=True)
            return await self._compute_minimal_snapshot(snapshot_date)

    def _assess_data_quality(self, indicators: Dict[str, Any]) -> DegradationLevel:
        """Assess data quality and determine degradation level."""
        required_fields = ['m2_yoy', 'pmi_manufacturing', 'cpi_yoy']

        available = sum(1 for f in required_fields if indicators.get(f) is not None)
        total = len(required_fields)

        if available == total:
            return DegradationLevel.FULL
        elif available >= total // 2:
            return DegradationLevel.PARTIAL
        elif available > 0:
            return DegradationLevel.LIMITED
        else:
            return DegradationLevel.MINIMAL

    async def _compute_full_snapshot(self, snapshot_date: date,
                                     indicators: Dict[str, Any]) -> MacroSnapshot:
        """Compute snapshot with all data available."""
        logger.info("Computing full macro snapshot (all data available)")

        # Score all dimensions
        scores = self.scorer.score_all(indicators)

        # Quadrant analysis - use M2 for monetary, approximate credit from growth data
        social_fin_proxy = indicators.get('gdp_yoy', 5.0) * 3  # Rough proxy
        quadrant_result = self.analyzer.analyze(
            m2_yoy=indicators.get('m2_yoy'),
            social_financing_yoy=social_fin_proxy,
            composite_score=scores['composite_score']
        )

        snapshot = MacroSnapshot(
            snapshot_date=snapshot_date,
            m2_yoy=indicators.get('m2_yoy'),
            dr007_avg=indicators.get('dr007_avg'),
            bond_10y_yield=indicators.get('bond_10y_yield'),
            liquidity_score=scores['liquidity_score'],

            gdp_yoy=indicators.get('gdp_yoy'),
            pmi_manufacturing=indicators.get('pmi_manufacturing'),
            industrial_prod_yoy=indicators.get('industrial_prod_yoy'),
            growth_score=scores['growth_score'],

            cpi_yoy=indicators.get('cpi_yoy'),
            ppi_yoy=indicators.get('ppi_yoy'),
            inflation_score=scores['inflation_score'],

            policy_score=scores['policy_score'],

            fed_rate=indicators.get('fed_rate'),
            dxy_index=indicators.get('dxy_index'),
            us_cn_spread=indicators.get('us_cn_spread'),
            global_score=scores['global_score'],

            composite_score=scores['composite_score'],
            monetary_condition=self._to_monetary_enum(quadrant_result.monetary_condition),
            credit_condition=self._to_credit_enum(quadrant_result.credit_condition),
            quadrant=self._to_quadrant_enum(quadrant_result.quadrant),
            macro_multiplier=quadrant_result.macro_multiplier
        )

        return snapshot

    async def _compute_partial_snapshot(self, snapshot_date: date,
                                        indicators: Dict[str, Any]) -> MacroSnapshot:
        """Compute snapshot with partial data, impute missing from prior."""
        logger.warning("Computing partial macro snapshot (imputing missing data)")

        # Fetch prior snapshot
        prior = await self.get_latest_snapshot()

        if prior is None:
            logger.warning("No prior snapshot for imputation, falling back to MINIMAL")
            return await self._compute_minimal_snapshot(snapshot_date)

        # Impute missing fields from prior
        if indicators.get('m2_yoy') is None and prior.m2_yoy is not None:
            indicators['m2_yoy'] = float(prior.m2_yoy)
        if indicators.get('pmi_manufacturing') is None and prior.pmi_manufacturing is not None:
            indicators['pmi_manufacturing'] = float(prior.pmi_manufacturing)
        if indicators.get('cpi_yoy') is None and prior.cpi_yoy is not None:
            indicators['cpi_yoy'] = float(prior.cpi_yoy)

        # Score with imputed data
        scores = self.scorer.score_all(indicators)

        # Apply penalty for imputation uncertainty
        adjusted_composite = scores['composite_score'] * self.PARTIAL_PENALTY
        logger.warning(f"Partial data penalty applied: composite adjusted to {adjusted_composite:.2f}")

        # Quadrant analysis
        social_fin_proxy = indicators.get('gdp_yoy', 5.0) * 3
        quadrant_result = self.analyzer.analyze(
            m2_yoy=indicators.get('m2_yoy'),
            social_financing_yoy=social_fin_proxy,
            composite_score=adjusted_composite
        )

        snapshot = MacroSnapshot(
            snapshot_date=snapshot_date,
            m2_yoy=indicators.get('m2_yoy'),
            dr007_avg=indicators.get('dr007_avg'),
            bond_10y_yield=indicators.get('bond_10y_yield'),
            liquidity_score=scores['liquidity_score'],
            gdp_yoy=indicators.get('gdp_yoy'),
            pmi_manufacturing=indicators.get('pmi_manufacturing'),
            industrial_prod_yoy=indicators.get('industrial_prod_yoy'),
            growth_score=scores['growth_score'],
            cpi_yoy=indicators.get('cpi_yoy'),
            ppi_yoy=indicators.get('ppi_yoy'),
            inflation_score=scores['inflation_score'],
            policy_score=scores['policy_score'],
            fed_rate=indicators.get('fed_rate'),
            dxy_index=indicators.get('dxy_index'),
            us_cn_spread=indicators.get('us_cn_spread'),
            global_score=scores['global_score'],
            composite_score=adjusted_composite,
            monetary_condition=self._to_monetary_enum(quadrant_result.monetary_condition),
            credit_condition=self._to_credit_enum(quadrant_result.credit_condition),
            quadrant=self._to_quadrant_enum(quadrant_result.quadrant),
            macro_multiplier=quadrant_result.macro_multiplier
        )

        return snapshot

    async def _compute_limited_snapshot(self, snapshot_date: date) -> MacroSnapshot:
        """Compute snapshot when all indicators unavailable, use prior + decay."""
        logger.warning("Computing limited macro snapshot (prior + decay)")

        prior = await self.get_latest_snapshot()

        if prior is None:
            logger.warning("No prior snapshot, falling back to MINIMAL")
            return await self._compute_minimal_snapshot(snapshot_date)

        # Apply decay to prior composite score
        decayed_score = float(prior.composite_score) * self.DECAY_FACTOR
        logger.warning(f"Decay applied: prior={prior.composite_score:.2f}, decayed={decayed_score:.2f}")

        # Compute multiplier from decayed score
        multiplier = self.analyzer.compute_multiplier(decayed_score)

        snapshot = MacroSnapshot(
            snapshot_date=snapshot_date,
            m2_yoy=prior.m2_yoy,
            dr007_avg=prior.dr007_avg,
            bond_10y_yield=prior.bond_10y_yield,
            liquidity_score=prior.liquidity_score,
            gdp_yoy=prior.gdp_yoy,
            pmi_manufacturing=prior.pmi_manufacturing,
            industrial_prod_yoy=prior.industrial_prod_yoy,
            growth_score=prior.growth_score,
            cpi_yoy=prior.cpi_yoy,
            ppi_yoy=prior.ppi_yoy,
            inflation_score=prior.inflation_score,
            policy_score=prior.policy_score,
            fed_rate=prior.fed_rate,
            dxy_index=prior.dxy_index,
            us_cn_spread=prior.us_cn_spread,
            global_score=prior.global_score,
            composite_score=decayed_score,
            monetary_condition=prior.monetary_condition,
            credit_condition=prior.credit_condition,
            quadrant=prior.quadrant,
            macro_multiplier=multiplier
        )

        return snapshot

    async def _compute_minimal_snapshot(self, snapshot_date: date) -> MacroSnapshot:
        """Compute snapshot when no data and no prior available, return neutral."""
        logger.warning("Computing minimal macro snapshot (neutral default)")

        snapshot = MacroSnapshot(
            snapshot_date=snapshot_date,
            m2_yoy=None,
            dr007_avg=None,
            bond_10y_yield=None,
            liquidity_score=0.0,
            gdp_yoy=None,
            pmi_manufacturing=None,
            industrial_prod_yoy=None,
            growth_score=0.0,
            cpi_yoy=None,
            ppi_yoy=None,
            inflation_score=0.0,
            policy_score=0.0,
            fed_rate=None,
            dxy_index=None,
            us_cn_spread=None,
            global_score=0.0,
            composite_score=0.0,
            monetary_condition=MonetaryConditionEnum.neutral,
            credit_condition=CreditConditionEnum.neutral,
            quadrant=QuadrantEnum.wide_tight,  # Default neutral
            macro_multiplier=1.000
        )

        return snapshot

    async def get_latest_snapshot(self) -> Optional[MacroSnapshot]:
        """Get the most recent macro snapshot."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(MacroSnapshot).order_by(MacroSnapshot.snapshot_date.desc())
            )
            return result.scalar_one_or_none()

    async def get_snapshot_by_date(self, snapshot_date: date) -> Optional[MacroSnapshot]:
        """Get macro snapshot by specific date."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(MacroSnapshot).where(MacroSnapshot.snapshot_date == snapshot_date)
            )
            return result.scalar_one_or_none()

    async def _save_snapshot(self, snapshot: MacroSnapshot) -> None:
        """Save snapshot to database, upserting if exists."""
        async with async_session_maker() as session:
            # Check if exists
            existing = await session.execute(
                select(MacroSnapshot).where(MacroSnapshot.snapshot_date == snapshot.snapshot_date)
            )
            existing = existing.scalar_one_or_none()

            if existing:
                # Update existing
                for key, value in snapshot.__dict__.items():
                    if not key.startswith('_'):
                        setattr(existing, key, value)
                await session.merge(existing)
            else:
                # Insert new
                session.add(snapshot)

            await session.commit()

    def _to_monetary_enum(self, condition: MonetaryCondition) -> MonetaryConditionEnum:
        """Convert MonetaryCondition to SQLAlchemy enum."""
        return MonetaryConditionEnum[condition.name.lower()]

    def _to_credit_enum(self, condition: CreditCondition) -> CreditConditionEnum:
        """Convert CreditCondition to SQLAlchemy enum."""
        return CreditConditionEnum[condition.name.lower()]

    def _to_quadrant_enum(self, quadrant: Quadrant) -> QuadrantEnum:
        """Convert Quadrant to SQLAlchemy enum."""
        return QuadrantEnum[quadrant.name.lower()]
