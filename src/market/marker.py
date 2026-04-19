"""Stock recommendation marker classification service."""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select

from src.database.connection import async_session_maker
from src.market.models import RecommendationMarker


class MarkerClassifier:
    """Classify stock recommendation markers."""

    # Thresholds
    LOGIC_HIGH = Decimal("0.7")
    LOGIC_MEDIUM = Decimal("0.4")
    EXPOSURE_HIGH = Decimal("0.5")
    EXPOSURE_MEDIUM = Decimal("0.3")
    MARKET_HIGH = Decimal("0.6")

    def classify_marker(
        self,
        logic_score: Decimal,
        market_score: Decimal,
        exposure_coefficient: Decimal,
        catalyst_level: str,
    ) -> Tuple[str, str]:
        """
        Classify recommendation marker.

        Args:
            logic_score: Logic layer score (0.0000-1.0000)
            market_score: Market layer score (0.0000-1.0000)
            exposure_coefficient: Exposure coefficient (0.0000-1.0000)
            catalyst_level: Catalyst level (strong/medium/none)

        Returns:
            Tuple of (marker, reason)

        Classification rules:
            - 逻辑受益股 (Logic beneficiary): logic >= 0.7 AND exposure >= 0.5
            - 关联受益股 (Related beneficiary): logic >= 0.4 AND exposure >= 0.3
            - 情绪跟风股 (Sentiment follower): market >= 0.6 AND logic < 0.4
        """
        # Logic beneficiary: high logic score + high exposure
        if logic_score >= self.LOGIC_HIGH and exposure_coefficient >= self.EXPOSURE_HIGH:
            return (
                "逻辑受益股",
                f"高逻辑分 ({logic_score}) 且强暴露 ({exposure_coefficient})",
            )

        # Related beneficiary: medium logic score + medium exposure
        elif logic_score >= self.LOGIC_MEDIUM and exposure_coefficient >= self.EXPOSURE_MEDIUM:
            return (
                "关联受益股",
                f"中等逻辑分 ({logic_score}) 且中等暴露 ({exposure_coefficient})",
            )

        # Sentiment follower: high market score, low logic
        elif market_score >= self.MARKET_HIGH and logic_score < self.LOGIC_MEDIUM:
            return (
                "情绪跟风股",
                f"高市场分 ({market_score}) 但低逻辑分 ({logic_score})",
            )

        # Default based on logic score
        elif logic_score >= self.LOGIC_MEDIUM:
            return (
                "逻辑受益股",
                f"逻辑分 ({logic_score}) 支持",
            )
        else:
            return (
                "情绪跟风股",
                f"市场分 ({market_score}) 驱动",
            )

    def build_reason(
        self,
        marker: str,
        logic_score: Decimal,
        market_score: Decimal,
        exposure_coefficient: Decimal,
        catalyst_level: str,
    ) -> str:
        """Build detailed reason string.

        Args:
            marker: The marker classification
            logic_score: Logic layer score
            market_score: Market layer score
            exposure_coefficient: Exposure coefficient
            catalyst_level: Catalyst level

        Returns:
            Detailed reason string in Chinese
        """
        reasons = []

        # Logic component
        if logic_score >= self.LOGIC_HIGH:
            reasons.append(f"高逻辑分 ({logic_score})")
        elif logic_score >= self.LOGIC_MEDIUM:
            reasons.append(f"中等逻辑分 ({logic_score})")
        else:
            reasons.append(f"低逻辑分 ({logic_score})")

        # Market component
        if market_score >= self.MARKET_HIGH:
            reasons.append(f"高市场分 ({market_score})")

        # Exposure component
        if exposure_coefficient >= self.EXPOSURE_HIGH:
            reasons.append(f"强暴露 ({exposure_coefficient})")

        # Catalyst component
        if catalyst_level == "strong":
            reasons.append("强催化剂")
        elif catalyst_level == "medium":
            reasons.append("中等催化剂")

        return "，".join(reasons)


class MarkerService:
    """Manage recommendation marker snapshots."""

    def __init__(self):
        self.classifier = MarkerClassifier()

    async def generate_markers(self, snapshot_date: date) -> List[RecommendationMarker]:
        """Generate markers for all stocks on a given date.

        Args:
            snapshot_date: The date to generate markers for

        Returns:
            List of RecommendationMarker objects
        """
        from src.market.models import StockCompositeScore, StockLogicExposure, StockCatalyst

        # Get composite scores for the date
        async with async_session_maker() as session:
            result = await session.execute(
                select(StockCompositeScore).where(
                    StockCompositeScore.snapshot_date == snapshot_date
                )
            )
            scores = result.scalars().all()

        markers = []

        for score in scores:
            # Get exposure coefficient (use max exposure across logics)
            async with async_session_maker() as session:
                exposure_result = await session.execute(
                    select(StockLogicExposure)
                    .where(
                        StockLogicExposure.stock_code == score.stock_code,
                        StockLogicExposure.snapshot_date == snapshot_date,
                    )
                    .order_by(StockLogicExposure.exposure_coefficient.desc())
                    .limit(1)
                )
                exposure = exposure_result.scalars().first()
                exposure_coefficient = (
                    exposure.exposure_coefficient if exposure else Decimal("0")
                )

            # Get catalyst level
            async with async_session_maker() as session:
                catalyst_result = await session.execute(
                    select(StockCatalyst).where(
                        StockCatalyst.stock_code == score.stock_code,
                        StockCatalyst.snapshot_date == snapshot_date,
                    )
                )
                catalyst = catalyst_result.scalars().first()
                catalyst_level = catalyst.catalyst_level if catalyst else "none"

            # Classify marker
            marker, reason = self.classifier.classify_marker(
                score.logic_score or Decimal("0"),
                score.market_score or Decimal("0"),
                exposure_coefficient or Decimal("0"),
                catalyst_level,
            )

            rec = RecommendationMarker(
                stock_code=score.stock_code,
                snapshot_date=snapshot_date,
                marker=marker,
                marker_reason=reason,
                logic_score=score.logic_score,
                market_score=score.market_score,
                exposure_coefficient=exposure_coefficient,
            )

            markers.append(rec)

        # Persist markers
        await self._persist_batch(markers)
        return markers

    async def _persist_batch(self, markers: List[RecommendationMarker]) -> None:
        """Persist markers to database.

        Args:
            markers: List of RecommendationMarker objects to persist
        """
        async with async_session_maker() as session:
            session.add_all(markers)
            await session.commit()

    async def get_stock_marker(
        self, stock_code: str, snapshot_date: date
    ) -> Optional[RecommendationMarker]:
        """Get marker for a specific stock.

        Args:
            stock_code: Stock code (e.g., "000001.SZ")
            snapshot_date: Date of marker snapshot

        Returns:
            RecommendationMarker or None if not found
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(RecommendationMarker).where(
                    RecommendationMarker.stock_code == stock_code,
                    RecommendationMarker.snapshot_date == snapshot_date,
                )
            )
            return result.scalar_one_or_none()
