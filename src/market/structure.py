"""Structure marker service for sector structure classification.

This module implements sector structure markers:
- 聚焦 (concentrated): High concentration + low breadth
- 扩散 (diffuse): Low concentration + high breadth
- 快速轮动 (rapid rotation): High turnover
- 正常 (normal): Default state
"""

from datetime import date
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.market.sector_radar import StockData


@dataclass
class StructureMarker:
    """Sector structure marker."""

    sector_id: str
    snapshot_date: date
    marker: str  # 聚焦/扩散/快速轮动/正常
    concentration: Decimal
    breadth: Decimal
    turnover: Decimal
    confidence: float


class StructureMarkerService:
    """Determine sector structure markers."""

    # Thresholds for classification
    CONCENTRATION_HIGH = Decimal("0.6")
    CONCENTRATION_LOW = Decimal("0.4")
    BREADTH_HIGH = Decimal("0.6")
    BREADTH_LOW = Decimal("0.4")
    TURNOVER_HIGH = Decimal("1.5")  # 50% above average

    def __init__(self):
        pass

    def determine_marker(
        self,
        concentration: Decimal,
        breadth: Decimal,
        turnover: Decimal
    ) -> str:
        """Determine structure marker.

        Args:
            concentration: Lead concentration (0-1) from MARKET-03
            breadth: Percentage of stocks above MA20 (0-1)
            turnover: Sector turnover rate vs historical (1.0 = average)

        Returns:
            "聚焦" | "扩散" | "快速轮动" | "正常"

        Classification logic:
        - 聚焦：concentration > 0.6 AND breadth < 0.4
        - 扩散：concentration < 0.4 AND breadth > 0.6
        - 快速轮动：turnover > 1.5
        - 正常：default
        """
        if concentration > self.CONCENTRATION_HIGH and breadth < self.BREADTH_LOW:
            return "聚焦"  # Leadership concentrated, narrow breadth
        elif concentration < self.CONCENTRATION_LOW and breadth > self.BREADTH_HIGH:
            return "扩散"  # Broad participation
        elif turnover > self.TURNOVER_HIGH:
            return "快速轮动"  # High turnover
        else:
            return "正常"

    def calculate_confidence(
        self,
        concentration: Decimal,
        breadth: Decimal,
        turnover: Decimal,
        marker: str
    ) -> float:
        """Calculate confidence in marker assignment.

        Confidence is based on how far the metrics are from the boundaries.
        Higher distance = higher confidence.

        Args:
            concentration: Lead concentration (0-1)
            breadth: Percentage of stocks above MA20 (0-1)
            turnover: Sector turnover rate vs historical
            marker: The assigned marker

        Returns:
            Confidence value (typically 0.0 to 1.0, can be negative near boundaries)
        """
        if marker == "聚焦":
            # How far into the 聚焦 region
            conc_dist = float(concentration - self.CONCENTRATION_HIGH)
            breadth_dist = float(self.BREADTH_LOW - breadth)
            # Return minimum distance (limiting factor)
            return min(conc_dist, breadth_dist)

        elif marker == "扩散":
            # How far into the 扩散 region
            conc_dist = float(self.CONCENTRATION_LOW - concentration)
            breadth_dist = float(breadth - self.BREADTH_HIGH)
            return min(conc_dist, breadth_dist)

        elif marker == "快速轮动":
            # How far above the turnover threshold
            turnover_dist = float(turnover - self.TURNOVER_HIGH)
            # Normalize by threshold to get relative confidence
            return turnover_dist / float(self.TURNOVER_HIGH)

        else:  # 正常
            # Normal - distance from any boundary
            # Calculate distance to nearest boundary
            dist_to_focus_conc = float(concentration - self.CONCENTRATION_HIGH)  # negative when below
            dist_to_focus_breadth = float(self.BREADTH_LOW - breadth)  # negative when above
            dist_to_diffuse_conc = float(self.CONCENTRATION_LOW - concentration)  # negative when above
            dist_to_diffuse_breadth = float(breadth - self.BREADTH_HIGH)  # negative when below
            dist_to_rotation = float(self.TURNOVER_HIGH - turnover)  # negative when above

            # Find minimum positive distance (how far from becoming another marker)
            distances = [d for d in [
                -dist_to_focus_conc,  # distance to focus concentration threshold
                -dist_to_focus_breadth,  # distance to focus breadth threshold
                -dist_to_diffuse_conc,  # distance to diffuse concentration threshold
                -dist_to_diffuse_breadth,  # distance to diffuse breadth threshold
                dist_to_rotation,  # distance to rotation turnover threshold
            ] if d > 0]

            if distances:
                return min(distances)
            return 0.5  # Default moderate confidence when in middle of normal region

    def calculate_breadth(self, stocks: List["StockData"]) -> Decimal:
        """Calculate breadth as percentage of stocks above MA20.

        Args:
            stocks: List of stock data with MA20 information

        Returns:
            Breadth value (0.0 to 1.0)
        """
        if not stocks:
            return Decimal("0")

        above_ma20_count = sum(1 for s in stocks if s.above_ma20)
        return Decimal(str(above_ma20_count)) / Decimal(str(len(stocks)))

    async def generate_marker(
        self,
        sector_id: str,
        snapshot_date: date,
        stocks: List["StockData"],
        concentration: Optional[Decimal] = None,
        turnover: Optional[Decimal] = None
    ) -> StructureMarker:
        """Generate structure marker for a sector.

        Args:
            sector_id: Sector identifier
            snapshot_date: Date of snapshot
            stocks: List of stock data in the sector
            concentration: Optional pre-calculated concentration (from MARKET-03)
            turnover: Optional pre-calculated turnover rate

        Returns:
            StructureMarker object
        """
        # Get inputs
        if concentration is None:
            concentration = await self._get_concentration(sector_id, snapshot_date)
        if turnover is None:
            turnover = await self._get_turnover(sector_id, snapshot_date)

        # Calculate breadth from stocks
        breadth = self.calculate_breadth(stocks)

        # Determine marker
        marker = self.determine_marker(concentration, breadth, turnover)

        # Calculate confidence
        confidence = self.calculate_confidence(concentration, breadth, turnover, marker)

        return StructureMarker(
            sector_id=sector_id,
            snapshot_date=snapshot_date,
            marker=marker,
            concentration=concentration,
            breadth=breadth,
            turnover=turnover,
            confidence=confidence
        )

    async def _get_concentration(self, sector_id: str, snapshot_date: date) -> Decimal:
        """Get lead concentration from MARKET-03 service.

        Placeholder - in production, integrate with concentration service.
        """
        # Placeholder: return neutral concentration
        return Decimal("0.5")

    async def _get_turnover(self, sector_id: str, snapshot_date: date) -> Decimal:
        """Get sector turnover rate.

        Placeholder - in production, calculate from volume data.
        """
        # Placeholder: return average turnover
        return Decimal("1.0")


class StructureQueries:
    """Query structure markers."""

    def __init__(self, db_session=None):
        """Initialize with optional database session."""
        self.db_session = db_session

    async def get_current_markers(self) -> Dict[str, str]:
        """Get current structure markers for all sectors.

        Returns:
            Dict mapping sector_id to marker string
        """
        # Placeholder implementation
        # In production: query sector_scores table for latest date
        return {}

    async def get_sectors_by_marker(self, marker: str) -> List[str]:
        """Get sectors with a specific marker.

        Args:
            marker: Marker string (聚焦/扩散/快速轮动/正常)

        Returns:
            List of sector IDs with this marker
        """
        # Placeholder implementation
        current = await self.get_current_markers()
        return [sid for sid, m in current.items() if m == marker]

    async def get_marker_history(
        self,
        sector_id: str,
        days: int = 30
    ) -> List[Tuple[date, str]]:
        """Get structure marker history for a sector.

        Args:
            sector_id: Sector identifier
            days: Number of days of history to retrieve

        Returns:
            List of (date, marker) tuples
        """
        # Placeholder implementation
        # In production: query sector_scores table with date filter
        return []
