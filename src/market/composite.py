"""Composite score service for stock recommendation ranking.

This module implements STOCK-08: Composite Score calculation.
Formula: 50% logic score + 50% market score.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.models import StockCompositeScore, StockMarketScore, StockLogicScore


class CompositeScoreService:
    """Calculate stock composite scores.

    Composite score = (logic_score + market_score) / 2

    The 50/50 weighting provides balanced consideration of:
    - Fundamental/logic factors (policy, industry trends)
    - Market/technical factors (price action, sentiment)
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize with database session.

        Args:
            db_session: Async SQLAlchemy session
        """
        self.db_session = db_session

    def calculate_composite(
        self,
        logic_score: Decimal,
        market_score: Decimal
    ) -> Decimal:
        """Calculate composite score from logic and market scores.

        Args:
            logic_score: Stock logic score (0-1), from STOCK-04
            market_score: Stock market score (0-1), from STOCK-05

        Returns:
            Composite score (0-1)

        Formula:
            composite = (logic_score + market_score) / 2
        """
        return (logic_score + market_score) / Decimal("2")

    def calculate_rank(
        self,
        stock_code: str,
        composite_scores: Dict[str, Decimal]
    ) -> int:
        """Calculate recommendation rank for a stock.

        Args:
            stock_code: Stock code to rank
            composite_scores: Dict[stock_code, composite_score] for all stocks

        Returns:
            Rank (1 = highest composite score, 0 if stock not found)

        Note:
            Rank 1 means the stock has the highest composite score.
            Higher rank number = lower recommendation priority.
        """
        if stock_code not in composite_scores:
            return 0

        score = composite_scores[stock_code]

        # Count stocks with strictly higher scores
        rank = sum(1 for s in composite_scores.values() if s > score) + 1

        return rank

    async def _get_logic_scores(self, snapshot_date: date) -> Dict[str, Decimal]:
        """Get logic scores for all stocks on given date.

        Args:
            snapshot_date: Date to fetch scores for

        Returns:
            Dict[stock_code, logic_score]
        """
        result = await self.db_session.execute(
            select(StockLogicScore).where(
                StockLogicScore.snapshot_date == snapshot_date
            )
        )
        scores = result.scalars().all()

        return {
            s.stock_code: s.logic_score
            for s in scores
            if s.logic_score is not None
        }

    async def _get_market_scores(self, snapshot_date: date) -> Dict[str, Decimal]:
        """Get market scores for all stocks on given date.

        Args:
            snapshot_date: Date to fetch scores for

        Returns:
            Dict[stock_code, market_score]
        """
        from src.market.models import StockMarketScore

        result = await self.db_session.execute(
            select(StockMarketScore).where(
                StockMarketScore.snapshot_date == snapshot_date
            )
        )
        scores = result.scalars().all()

        return {
            s.stock_code: s.market_composite
            for s in scores
            if s.market_composite is not None
        }

    async def _persist_batch(self, records: List[StockCompositeScore]) -> None:
        """Persist composite score records to database.

        Args:
            records: List of StockCompositeScore objects to persist
        """
        for record in records:
            self.db_session.add(record)
        await self.db_session.commit()

    async def generate_snapshot(
        self,
        snapshot_date: date
    ) -> List[StockCompositeScore]:
        """Generate composite score snapshots for all stocks.

        Args:
            snapshot_date: Date for snapshot

        Returns:
            List of StockCompositeScore records
        """
        # Get logic scores
        logic_scores = await self._get_logic_scores(snapshot_date)

        # Get market scores
        market_scores = await self._get_market_scores(snapshot_date)

        # Calculate composites
        composites: Dict[str, Decimal] = {}
        records: List[StockCompositeScore] = []

        all_stocks = set(logic_scores.keys()) | set(market_scores.keys())

        for stock_code in all_stocks:
            logic = logic_scores.get(stock_code, Decimal("0"))
            market = market_scores.get(stock_code, Decimal("0"))

            composite = self.calculate_composite(logic, market)
            composites[stock_code] = composite

        # Calculate ranks
        for stock_code, composite in composites.items():
            rank = self.calculate_rank(stock_code, composites)

            record = StockCompositeScore(
                stock_code=stock_code,
                snapshot_date=snapshot_date,
                logic_score=logic_scores.get(stock_code, Decimal("0")),
                market_score=market_scores.get(stock_code, Decimal("0")),
                composite_score=composite,
                recommendation_rank=rank
            )

            records.append(record)

        # Persist all
        await self._persist_batch(records)
        return records


class CompositeQueries:
    """Query composite scores.

    Provides read access to composite score data for:
    - Generating top stock recommendations
    - Looking up individual stock scores
    - Filtering by rank ranges
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize with database session.

        Args:
            db_session: Async SQLAlchemy session
        """
        self.db_session = db_session

    async def get_top_stocks(
        self,
        snapshot_date: date,
        limit: int = 20
    ) -> List[StockCompositeScore]:
        """Get top N stocks by composite score.

        Args:
            snapshot_date: Date to query
            limit: Maximum number of stocks to return (default 20)

        Returns:
            List of StockCompositeScore records, ordered by composite_score DESC
        """
        result = await self.db_session.execute(
            select(StockCompositeScore)
            .where(StockCompositeScore.snapshot_date == snapshot_date)
            .order_by(StockCompositeScore.composite_score.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_stock_composite(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> Optional[StockCompositeScore]:
        """Get composite score for a specific stock.

        Args:
            stock_code: Stock code to lookup
            snapshot_date: Date to query

        Returns:
            StockCompositeScore if found, None otherwise
        """
        result = await self.db_session.execute(
            select(StockCompositeScore).where(
                StockCompositeScore.stock_code == stock_code,
                StockCompositeScore.snapshot_date == snapshot_date
            )
        )
        return result.scalar_one_or_none()

    async def get_stocks_by_rank_range(
        self,
        snapshot_date: date,
        min_rank: int,
        max_rank: int
    ) -> List[StockCompositeScore]:
        """Get stocks within a rank range.

        Args:
            snapshot_date: Date to query
            min_rank: Minimum rank (inclusive)
            max_rank: Maximum rank (inclusive)

        Returns:
            List of StockCompositeScore records within rank range,
            ordered by recommendation_rank ASC
        """
        result = await self.db_session.execute(
            select(StockCompositeScore)
            .where(StockCompositeScore.snapshot_date == snapshot_date)
            .where(StockCompositeScore.recommendation_rank >= min_rank)
            .where(StockCompositeScore.recommendation_rank <= max_rank)
            .order_by(StockCompositeScore.recommendation_rank)
        )
        return result.scalars().all()
