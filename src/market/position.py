"""Position calculation service with sigmoid-based scaling and overlays."""

import math
from decimal import Decimal
from typing import Dict

from src.market.models import SectorState


class PositionCalculator:
    """Calculate continuous position recommendations.

    EXEC-01: Continuous Position Function
    Implements sigmoid-based position calculation with macro and sector overlays.
    """

    # Position tier boundaries
    TIER_EMPTY = Decimal("0.10")    # 0-10%: 空仓
    TIER_LIGHT = Decimal("0.30")    # 10-30%: 轻仓
    TIER_MODERATE = Decimal("0.60") # 30-60%: 中等
    TIER_HEAVY = Decimal("0.80")    # 60-80%: 重仓
    # 80-100%: 满仓

    # Sector state multipliers
    STATE_MULTIPLIERS: Dict[SectorState, Decimal] = {
        SectorState.weak: Decimal("0.5"),
        SectorState.normal: Decimal("1.0"),
        SectorState.overheated: Decimal("0.7"),
    }

    def sigmoid(self, x: Decimal) -> Decimal:
        """Sigmoid function for smooth 0-1 scaling.

        Args:
            x: Input value (typically -1 to 1 range)

        Returns:
            Sigmoid output in 0-1 range
        """
        return Decimal(str(1 / (1 + math.exp(-float(x)))))

    def calculate_base_position(self, composite_score: Decimal) -> Decimal:
        """Calculate base position from composite score using sigmoid scaling.

        Args:
            composite_score: Score in 0-1 range

        Returns:
            Base position percentage in 0-1 range
        """
        # Map 0-1 to sigmoid input range of -1 to 1
        sigmoid_input = composite_score * 2 - 1
        return self.sigmoid(sigmoid_input)

    def apply_macro_overlay(
        self,
        base_position: Decimal,
        macro_multiplier: Decimal
    ) -> Decimal:
        """Apply macro multiplier overlay.

        Args:
            base_position: Base position from sigmoid
            macro_multiplier: Macro multiplier (0.5-1.5)

        Returns:
            Position adjusted for macro conditions
        """
        return base_position * macro_multiplier

    def apply_sector_overlay(
        self,
        position: Decimal,
        sector_state: SectorState
    ) -> Decimal:
        """Apply sector state overlay.

        Args:
            position: Position after macro overlay
            sector_state: Sector state (weak/normal/overheated)

        Returns:
            Position adjusted for sector conditions
        """
        multiplier = self.STATE_MULTIPLIERS.get(
            sector_state, Decimal("1.0")
        )
        return position * multiplier

    def calculate_position(
        self,
        composite_score: Decimal,
        macro_multiplier: Decimal,
        sector_state: SectorState
    ) -> Decimal:
        """Calculate full position recommendation.

        Args:
            composite_score: Composite score from STOCK-08 (0-1)
            macro_multiplier: Macro multiplier from MACRO-02 (0.5-1.5)
            sector_state: Sector state from MARKET-02

        Returns:
            Position percentage clamped to 0.0-1.0
        """
        base = self.calculate_base_position(composite_score)
        macro_adjusted = self.apply_macro_overlay(base, macro_multiplier)
        final = self.apply_sector_overlay(macro_adjusted, sector_state)

        # Clamp to valid range
        return max(Decimal("0"), min(Decimal("1"), final))

    def get_position_tier(self, position: Decimal) -> str:
        """Map position to tier name.

        Position tiers:
        - 空仓 (empty): 0-10%
        - 轻仓 (light): 10-30%
        - 中等 (moderate): 30-60%
        - 重仓 (heavy): 60-80%
        - 满仓 (full): 80-100%

        Args:
            position: Position percentage (0-1)

        Returns:
            Tier name in Chinese
        """
        if position < self.TIER_EMPTY:
            return "空仓"
        elif position < self.TIER_LIGHT:
            return "轻仓"
        elif position < self.TIER_MODERATE:
            return "中等"
        elif position < self.TIER_HEAVY:
            return "重仓"
        else:
            return "满仓"
