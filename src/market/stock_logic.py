"""Stock Logic Score calculation for STOCK-04.

This module implements the stock logic score calculation that aggregates
logic scores weighted by exposure coefficients.

Formula:
    stock_logic_score = sum(logic_score.decayed_score * exposure) / sum(exposure)
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, NamedTuple, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import LogicScore
from src.market.models import StockLogicScore


class LogicContribution(NamedTuple):
    """Contribution of a single logic to the stock logic score."""
    logic_id: str
    logic_score: Decimal
    exposure: Decimal
    contribution: Decimal


class StockLogicBreakdown(NamedTuple):
    """Detailed breakdown of stock logic score calculation."""
    final_score: Decimal
    total_exposure: Decimal
    contributions: List[LogicContribution]


class StockLogicScoreCalculator:
    """Calculate stock logic scores from exposure-weighted logic scores.

    The calculator implements exposure-weighted averaging:
    - Each logic score is weighted by its exposure coefficient
    - Final score is normalized by total exposure
    - Score is capped at 1.0
    """

    def calculate(
        self,
        logic_scores: Dict[str, LogicScore],
        exposures: Dict[str, Decimal]
    ) -> Decimal:
        """
        Calculate stock logic score.

        Args:
            logic_scores: Dict[logic_id, LogicScore]
            exposures: Dict[logic_id, exposure_coefficient]

        Returns:
            stock_logic_score (0-1)

        Formula:
            total_weighted = sum(decayed_score * exposure for each logic)
            total_exposure = sum(exposure for each logic)
            stock_logic_score = total_weighted / total_exposure
        """
        total_weighted = Decimal("0")
        total_exposure = Decimal("0")

        for logic_id, score in logic_scores.items():
            exposure = exposures.get(logic_id, Decimal("0"))

            if exposure > 0 and score.decayed_score is not None:
                total_weighted += score.decayed_score * exposure
                total_exposure += exposure

        if total_exposure == Decimal("0"):
            return Decimal("0")

        result = total_weighted / total_exposure
        return min(result, Decimal("1.0"))

    def calculate_with_breakdown(
        self,
        logic_scores: Dict[str, LogicScore],
        exposures: Dict[str, Decimal]
    ) -> StockLogicBreakdown:
        """
        Calculate score with detailed breakdown.

        Args:
            logic_scores: Dict[logic_id, LogicScore]
            exposures: Dict[logic_id, exposure_coefficient]

        Returns:
            StockLogicBreakdown with per-logic contributions

        The breakdown includes:
        - final_score: The calculated stock logic score
        - total_exposure: Sum of all exposures
        - contributions: List of per-logic contributions
        """
        contributions = []
        total_weighted = Decimal("0")
        total_exposure = Decimal("0")

        for logic_id, score in logic_scores.items():
            exposure = exposures.get(logic_id, Decimal("0"))

            if exposure > 0 and score.decayed_score is not None:
                contribution = score.decayed_score * exposure
                contributions.append(LogicContribution(
                    logic_id=logic_id,
                    logic_score=score.decayed_score,
                    exposure=exposure,
                    contribution=contribution
                ))
                total_weighted += contribution
                total_exposure += exposure

        final_score = Decimal("0") if total_exposure == Decimal("0") else min(
            total_weighted / total_exposure, Decimal("1.0")
        )

        return StockLogicBreakdown(
            final_score=final_score,
            total_exposure=total_exposure,
            contributions=contributions
        )


class StockLogicService:
    """Manage stock logic score generation.

    The service orchestrates:
    - Fetching logic scores for a given date
    - Fetching stock exposures for a given date
    - Calculating the weighted score
    - Persisting the snapshot to database
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        """Initialize the service.

        Args:
            db_session: Optional existing database session.
                       If not provided, creates a new session per operation.
        """
        self.calculator = StockLogicScoreCalculator()
        self._db_session = db_session

    async def _get_logic_scores(
        self,
        snapshot_date: date,
        session: AsyncSession
    ) -> Dict[str, LogicScore]:
        """Get all logic scores for a given date.

        Args:
            snapshot_date: Date to fetch scores for
            session: Database session

        Returns:
            Dict[logic_id, LogicScore]
        """
        result = await session.execute(
            select(LogicScore).where(
                LogicScore.snapshot_date == snapshot_date
            )
        )
        scores = result.scalars().all()

        return {
            s.logic_id: s
            for s in scores
            if s.decayed_score is not None
        }

    async def _get_stock_exposures(
        self,
        stock_code: str,
        snapshot_date: date,
        session: AsyncSession
    ) -> Dict[str, Decimal]:
        """Get exposure coefficients for a stock on a given date.

        Args:
            stock_code: Stock code
            snapshot_date: Date to fetch exposures for
            session: Database session

        Returns:
            Dict[logic_id, exposure_coefficient]
        """
        from src.market.models import StockLogicExposure

        result = await session.execute(
            select(StockLogicExposure).where(
                StockLogicExposure.stock_code == stock_code,
                StockLogicExposure.snapshot_date == snapshot_date
            )
        )
        exposures = result.scalars().all()

        return {
            e.logic_id: e.exposure_coefficient
            for e in exposures
            if e.exposure_coefficient is not None
        }

    async def _persist(
        self,
        snapshot: StockLogicScore,
        session: AsyncSession
    ) -> None:
        """Persist snapshot to database.

        Args:
            snapshot: StockLogicScore to persist
            session: Database session
        """
        session.add(snapshot)
        await session.commit()

    async def generate_snapshot(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> StockLogicScore:
        """Generate logic score snapshot for a stock.

        Args:
            stock_code: Stock code
            snapshot_date: Date for snapshot

        Returns:
            StockLogicScore record

        Process:
        1. Fetch all logic scores for the date
        2. Fetch stock's exposure coefficients
        3. Calculate weighted score
        4. Count contributing logics
        5. Persist snapshot
        """
        close_session = False
        if self._db_session is None:
            session = async_session_maker()
            close_session = True
        else:
            session = self._db_session

        try:
            async with session:
                # Get logic scores for date
                logic_scores = await self._get_logic_scores(snapshot_date, session)

                # Get stock exposures
                exposures = await self._get_stock_exposures(stock_code, snapshot_date, session)

                # Calculate score
                score = self.calculator.calculate(logic_scores, exposures)

                # Count contributing logics (logics with exposure > 0)
                contributing = sum(1 for e in exposures.values() if e > Decimal("0"))

                # Create and persist snapshot
                snapshot = StockLogicScore(
                    stock_code=stock_code,
                    snapshot_date=snapshot_date,
                    logic_score=score,
                    total_exposure=sum(exposures.values()) if exposures else Decimal("0"),
                    contributing_logics=contributing,
                )

                await self._persist(snapshot, session)
                return snapshot
        finally:
            if close_session:
                await session.close()
