"""Leader identification service for dragon/zhongjun/follower classification."""

from datetime import date
from decimal import Decimal
from typing import List, Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .models import StockLeaderRole, LeaderRole, StockSectorMapping


class LeaderIdentificationService:
    """Identify stock leader roles within sectors.

    Classification logic:
    - Dragon leader (龙头): First to limit-up, highest consecutive gains
    - Zhongjun (中军): Large cap, stable gains, high volume
    - Follower (跟风): Neither dragon nor zhongjun
    """

    # Thresholds for role classification
    DRAGON_THRESHOLD = Decimal("5.0")
    ZHONGJUN_THRESHOLD = Decimal("3.0")

    def calculate_dragon_score(
        self,
        limit_up_count: int = 0,
        consecutive_gains: int = 0,
        is_first_limit: bool = False,
    ) -> Decimal:
        """Calculate dragon leader score.

        Args:
            limit_up_count: Number of limit-ups in past 5 days
            consecutive_gains: Number of consecutive gain days
            is_first_limit: Whether this stock was first to limit-up in sector

        Returns:
            Dragon score (higher = more likely to be dragon leader)

        Formula:
            dragon_score = limit_up_count * 2 + consecutive_gains + (3 if is_first_limit else 0)
        """
        # Limit-up count (weighted 2x)
        limit_up_score = Decimal(str(limit_up_count)) * Decimal("2")

        # Consecutive gains
        consecutive_score = Decimal(str(consecutive_gains))

        # First to limit-up bonus
        first_limit_bonus = Decimal("3") if is_first_limit else Decimal("0")

        # Total
        return limit_up_score + consecutive_score + first_limit_bonus

    def calculate_zhongjun_score(
        self,
        market_cap_rank: Optional[int],
        volume_stability: float = 0.5,
        trend_consistency: float = 0.5,
        sector_stocks_count: int = 0,
    ) -> Decimal:
        """Calculate zhongjun (anchor) score.

        Args:
            market_cap_rank: Market cap rank within sector (1 = largest)
            volume_stability: Volume stability metric (0-1, higher = more stable)
            trend_consistency: Trend consistency metric (0-1, higher = more consistent)
            sector_stocks_count: Total number of stocks in sector

        Returns:
            Zhongjun score (higher = more likely to be zhongjun)

        Formula:
            zhongjun_score = (sector_rank_score * 3) + (volume_stability * 2) + (trend_consistency * 2)
        """
        # Market cap rank (invert: rank 1 = highest score)
        if market_cap_rank is not None and sector_stocks_count > 0:
            # Convert rank to normalized score (rank 1 = 1.0, last rank = 0.0)
            rank_score = (sector_stocks_count - market_cap_rank + 1) / sector_stocks_count
            cap_score = Decimal(str(rank_score)) * Decimal("3")
        else:
            cap_score = Decimal("0")

        # Volume stability (low variance = high score)
        volume_score = Decimal(str(volume_stability)) * Decimal("2")

        # Trend consistency (MA alignment consistency)
        trend_score = Decimal(str(trend_consistency)) * Decimal("2")

        return cap_score + volume_score + trend_score

    def identify_role(
        self,
        dragon_score: Decimal,
        zhongjun_score: Decimal,
    ) -> Tuple[LeaderRole, Decimal, Decimal]:
        """Identify stock's role within sector.

        Args:
            dragon_score: Calculated dragon score
            zhongjun_score: Calculated zhongjun score

        Returns:
            Tuple of (role, dragon_score, zhongjun_score)
        """
        if dragon_score >= self.DRAGON_THRESHOLD:
            return LeaderRole.dragon, dragon_score, zhongjun_score
        elif zhongjun_score >= self.ZHONGJUN_THRESHOLD:
            return LeaderRole.zhongjun, dragon_score, zhongjun_score
        else:
            return LeaderRole.follower, dragon_score, zhongjun_score

    def calculate_confidence(
        self,
        role: LeaderRole,
        dragon_score: Decimal,
        zhongjun_score: Decimal,
    ) -> float:
        """Calculate confidence in role assignment.

        Args:
            role: Assigned role
            dragon_score: Dragon score
            zhongjun_score: Zhongjun score

        Returns:
            Confidence value (0.0-1.0 for dragon/zhongjun, 0.0-1.0 for follower)
        """
        if role == LeaderRole.dragon:
            # How far above dragon threshold (normalized)
            return min(
                float((dragon_score - self.DRAGON_THRESHOLD) / self.DRAGON_THRESHOLD),
                1.0,
            )
        elif role == LeaderRole.zhongjun:
            # How far above zhongjun threshold (normalized)
            return min(
                float((zhongjun_score - self.ZHONGJUN_THRESHOLD) / self.ZHONGJUN_THRESHOLD),
                1.0,
            )
        else:
            # Follower - distance from thresholds (normalized)
            dragon_dist = float(self.DRAGON_THRESHOLD - dragon_score)
            zhongjun_dist = float(self.ZHONGJUN_THRESHOLD - zhongjun_score)
            # Normalize by threshold
            return min(min(dragon_dist, zhongjun_dist) / float(self.DRAGON_THRESHOLD), 1.0)


class LeaderService:
    """Manage leader role snapshots."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.identifier = LeaderIdentificationService()

    async def generate_snapshot(
        self,
        sector_id: str,
        snapshot_date: date,
        stocks_data: List[dict],
    ) -> List[StockLeaderRole]:
        """Generate leader role snapshots for all stocks in a sector.

        Args:
            sector_id: Sector ID to process
            snapshot_date: Date for the snapshot
            stocks_data: List of stock data dictionaries with keys:
                - ts_code: Stock code
                - limit_up_count: Limit-up count (past 5 days)
                - consecutive_gains: Consecutive gain days
                - is_first_limit: Whether first to limit-up
                - market_cap_rank: Market cap rank in sector
                - volume_stability: Volume stability (0-1)
                - trend_consistency: Trend consistency (0-1)

        Returns:
            List of StockLeaderRole records
        """
        if not stocks_data:
            return []

        sector_stocks_count = len(stocks_data)

        # Calculate roles for all stocks
        roles = []
        for stock in stocks_data:
            # Calculate scores
            dragon_score = self.identifier.calculate_dragon_score(
                limit_up_count=stock.get("limit_up_count", 0),
                consecutive_gains=stock.get("consecutive_gains", 0),
                is_first_limit=stock.get("is_first_limit", False),
            )

            zhongjun_score = self.identifier.calculate_zhongjun_score(
                market_cap_rank=stock.get("market_cap_rank"),
                volume_stability=stock.get("volume_stability", 0.5),
                trend_consistency=stock.get("trend_consistency", 0.5),
                sector_stocks_count=sector_stocks_count,
            )

            # Identify role
            role, _, _ = self.identifier.identify_role(dragon_score, zhongjun_score)

            # Calculate confidence
            confidence = self.identifier.calculate_confidence(
                role, dragon_score, zhongjun_score
            )

            # Create record
            record = StockLeaderRole(
                stock_code=stock.get("ts_code"),
                sector_id=sector_id,
                snapshot_date=snapshot_date,
                role=role.value,
                dragon_score=dragon_score,
                zhongjun_score=zhongjun_score,
                confidence=confidence,
            )

            roles.append(record)

        # Persist all
        await self._persist_batch(roles)
        return roles

    async def _persist_batch(self, roles: List[StockLeaderRole]) -> None:
        """Persist batch of leader role records to database."""
        for role in roles:
            self.session.add(role)

        await self.session.commit()
