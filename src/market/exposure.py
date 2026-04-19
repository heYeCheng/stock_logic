"""Exposure coefficient calculation for stock-logic exposure mapping."""

from datetime import date
from decimal import Decimal
from typing import List, Dict, Optional, Set

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.market.models import StockLogicExposure, StockSectorMapping
from src.logic.models import LogicModel


class ExposureCalculator:
    """Calculate stock exposure to logics.

    Exposure coefficient = affiliation_strength × logic_match_score

    Where:
    - affiliation_strength: Maximum affiliation strength across stock's sectors
    - logic_match_score: Keyword overlap ratio between stock and logic
    """

    def calculate_exposure(
        self,
        stock_keywords: Set[str],
        sector_affiliations: List[StockSectorMapping],
        logic_keywords: Set[str]
    ) -> Decimal:
        """
        Calculate exposure coefficient for a single stock-logic pair.

        Args:
            stock_keywords: Keywords associated with stock
            sector_affiliations: Stock's sector mappings
            logic_keywords: Keywords from logic

        Returns:
            Exposure coefficient (0-1)

        Formula:
            max_affiliation = max(affiliation_strength for all sector mappings)
            logic_match_score = overlap / len(logic_keywords)
            exposure = max_affiliation * logic_match_score
        """
        # Get max affiliation strength
        if not sector_affiliations:
            max_affiliation = Decimal("0")
        else:
            max_affiliation = max(
                m.affiliation_strength for m in sector_affiliations
            )

        # Calculate logic match score (keyword overlap)
        if not logic_keywords or not stock_keywords:
            logic_match_score = Decimal("0")
        else:
            overlap = len(logic_keywords & stock_keywords)
            logic_match_score = Decimal(str(overlap / len(logic_keywords)))

        # Compute exposure
        exposure = max_affiliation * logic_match_score

        return min(exposure, Decimal("1.0"))

    def calculate_batch_exposure(
        self,
        stock_keywords_map: Dict[str, Set[str]],
        sector_mappings_map: Dict[str, List[StockSectorMapping]],
        logics: List[LogicModel]
    ) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate exposure for all stock-logic pairs.

        Args:
            stock_keywords_map: Dict[stock_code, set of keywords]
            sector_mappings_map: Dict[stock_code, list of sector mappings]
            logics: List of LogicModel objects

        Returns:
            Dict[stock_code, Dict[logic_id, exposure]]
        """
        result = {}

        for stock_code, keywords in stock_keywords_map.items():
            result[stock_code] = {}
            affiliations = sector_mappings_map.get(stock_code, [])

            for logic in logics:
                logic_keywords = set(logic.keywords or []) if logic.keywords else set()
                exposure = self.calculate_exposure(
                    keywords,
                    affiliations,
                    logic_keywords
                )
                result[stock_code][logic.logic_id] = exposure

        return result


class ExposureQueries:
    """Query exposure data."""

    @staticmethod
    async def get_stock_exposures(
        stock_code: str,
        snapshot_date: date,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Decimal]:
        """Get all logic exposures for a stock on a given date.

        Args:
            stock_code: The stock code
            snapshot_date: The snapshot date
            session: Optional existing session

        Returns:
            Dict[logic_id, exposure_coefficient]
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockLogicExposure)
                    .where(
                        and_(
                            StockLogicExposure.stock_code == stock_code,
                            StockLogicExposure.snapshot_date == snapshot_date
                        )
                    )
                )
                exposures = result.scalars().all()
                return {
                    e.logic_id: e.exposure_coefficient
                    for e in exposures
                }
        finally:
            if close_session:
                await session.close()

    @staticmethod
    async def get_logic_exposed_stocks(
        logic_id: str,
        snapshot_date: date,
        min_exposure: Decimal = Decimal("0.3"),
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """Get stocks with significant exposure to a logic.

        Args:
            logic_id: The logic ID
            snapshot_date: The snapshot date
            min_exposure: Minimum exposure threshold (default 0.3)
            session: Optional existing session

        Returns:
            List of stock codes with exposure >= min_exposure
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockLogicExposure.stock_code)
                    .where(
                        and_(
                            StockLogicExposure.logic_id == logic_id,
                            StockLogicExposure.snapshot_date == snapshot_date,
                            StockLogicExposure.exposure_coefficient >= min_exposure
                        )
                    )
                )
                return list(result.scalars().all())
        finally:
            if close_session:
                await session.close()

    @staticmethod
    async def get_max_exposure_stock(
        logic_id: str,
        snapshot_date: date,
        session: Optional[AsyncSession] = None
    ) -> Optional[str]:
        """Get stock with highest exposure to a logic.

        Args:
            logic_id: The logic ID
            snapshot_date: The snapshot date
            session: Optional existing session

        Returns:
            Stock code with highest exposure, or None if no data
        """
        close_session = False
        if session is None:
            session = async_session_maker()
            close_session = True

        try:
            async with session:
                result = await session.execute(
                    select(StockLogicExposure)
                    .where(
                        and_(
                            StockLogicExposure.logic_id == logic_id,
                            StockLogicExposure.snapshot_date == snapshot_date
                        )
                    )
                    .order_by(StockLogicExposure.exposure_coefficient.desc())
                    .limit(1)
                )
                exposure = result.scalar_one_or_none()
                return exposure.stock_code if exposure else None
        finally:
            if close_session:
                await session.close()
