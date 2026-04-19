"""Lead concentration calculation using Herfindahl-Hirschman Index (HHI).

Measures how concentrated sector leadership is - whether driven by few dragon leaders
or diffuse with broad participation.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import date

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from src.database.connection import async_session_maker
from src.market.models import SectorScore


class ConcentrationCalculator:
    """Calculate lead concentration using HHI."""

    def calculate(self, stocks: List[object]) -> Decimal:
        """
        Calculate concentration for a sector.

        Uses Herfindahl-Hirschman Index (HHI) on market scores.
        HHI = sum of squared market share percentages.
        Normalized to 0-1 scale where:
        - 1.0 = single stock dominates (max concentration)
        - 0.0 = perfectly equal distribution (min concentration)

        Args:
            stocks: List of stock objects with market_score attribute

        Returns:
            Normalized HHI (0-1)
        """
        # Filter to leader candidates
        candidates = [s for s in stocks if self._is_leader_candidate(s)]

        if not candidates:
            return Decimal("0")

        strengths = [s.market_score for s in candidates]
        total = sum(strengths)

        if total == 0:
            return Decimal("0")

        # Calculate shares (as Decimal for precision)
        shares = [Decimal(str(s)) / total for s in strengths]

        # HHI: sum of squared market shares
        hhi = sum(s ** 2 for s in shares)

        # Normalize to 0-1
        n = len(candidates)
        if n == 1:
            return Decimal("1")  # Single stock = max concentration

        min_hhi = Decimal(str(1 / n))
        normalized = (hhi - min_hhi) / (Decimal("1") - min_hhi)

        # Clamp to valid range (numerical stability)
        return max(Decimal("0"), min(Decimal("1"), normalized))

    def _is_leader_candidate(self, stock: object) -> bool:
        """Determine if stock is a leader candidate.

        Leader candidates are top performers by market score.
        Threshold: market_score > 0.5
        """
        return stock.market_score > Decimal("0.5")

    def interpret(self, concentration: Decimal) -> str:
        """Interpret concentration level.

        Args:
            concentration: Normalized HHI value (0-1)

        Returns:
            Interpretation string:
            - "high": Leadership concentrated in few stocks (龙头带动)
            - "medium": Balanced leadership
            - "low": Diffuse leadership, sector rotation (快速轮动)
        """
        if concentration > Decimal("0.6"):
            return "high"  # 龙头带动
        elif concentration > Decimal("0.3"):
            return "medium"  # Balanced
        else:
            return "low"  # 快速轮动


class ConcentrationQueries:
    """Query interface for concentration data."""

    def __init__(self, session=None):
        """Initialize with optional database session."""
        self.session = session

    async def get_sector_concentration(
        self, sector_id: str
    ) -> Optional[Decimal]:
        """Get current concentration for a sector.

        Args:
            sector_id: The sector identifier

        Returns:
            Current lead_concentration value or None if not found
        """
        # Placeholder - requires async session
        return None

    async def get_high_concentration_sectors(self) -> List[str]:
        """Get sectors with high concentration (>0.6).

        Returns:
            List of sector_ids with concentration > 0.6
        """
        # Placeholder implementation
        return []

    async def get_concentration_history(
        self,
        sector_id: str,
        days: int = 30
    ) -> List[Tuple[date, Decimal]]:
        """Get concentration history for a sector.

        Args:
            sector_id: The sector identifier
            days: Number of days to look back

        Returns:
            List of (snapshot_date, concentration) tuples
        """
        # Placeholder implementation
        return []
