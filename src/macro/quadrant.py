"""Monetary-credit quadrant determination and macro_multiplier calculation."""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class MonetaryCondition(Enum):
    """Monetary condition classification."""
    WIDE = "wide"
    NEUTRAL = "neutral"
    TIGHT = "tight"


class CreditCondition(Enum):
    """Credit condition classification."""
    WIDE = "wide"
    NEUTRAL = "neutral"
    TIGHT = "tight"


class Quadrant(Enum):
    """Monetary-credit quadrants."""
    WIDE_WIDE = "wide-wide"  # Risk ON, cyclicals
    WIDE_TIGHT = "wide-tight"  # Defensive
    TIGHT_WIDE = "tight-wide"  # Selective
    TIGHT_TIGHT = "tight-tight"  # Risk OFF


@dataclass
class QuadrantResult:
    """Result of quadrant analysis."""
    monetary_condition: MonetaryCondition
    credit_condition: CreditCondition
    quadrant: Quadrant
    macro_multiplier: float


class QuadrantAnalyzer:
    """Determine monetary-credit quadrant and compute macro_multiplier."""

    # Configurable thresholds for monetary condition (M2 YoY)
    M2_WIDE_THRESHOLD = 10.0  # M2 YoY > 10% = wide
    M2_TIGHT_THRESHOLD = 8.0  # M2 YoY < 8% = tight

    # Configurable thresholds for credit condition (Social Financing YoY)
    SOCIAL_FIN_WIDE = 15.0  # 社融 YoY > 15% = wide
    SOCIAL_FIN_TIGHT = 10.0  # 社融 YoY < 10% = tight

    # Macro multiplier bounds
    MULTIPLIER_MIN = 0.85
    MULTIPLIER_MAX = 1.15

    def determine_monetary_condition(self, m2_yoy: Optional[float]) -> MonetaryCondition:
        """
        Determine monetary condition from M2 YoY.

        Args:
            m2_yoy: M2 money supply YoY growth %

        Returns:
            MonetaryCondition: wide, neutral, or tight
        """
        if m2_yoy is None:
            logger.debug("M2 YoY not available, defaulting to neutral monetary condition")
            return MonetaryCondition.NEUTRAL

        if m2_yoy > self.M2_WIDE_THRESHOLD:
            condition = MonetaryCondition.WIDE
        elif m2_yoy < self.M2_TIGHT_THRESHOLD:
            condition = MonetaryCondition.TIGHT
        else:
            condition = MonetaryCondition.NEUTRAL

        logger.info(f"Monetary condition: M2 YoY={m2_yoy}% -> {condition.value}")
        return condition

    def determine_credit_condition(self, social_financing_yoy: Optional[float]) -> CreditCondition:
        """
        Determine credit condition from Social Financing YoY.

        Args:
            social_financing_yoy: Total social financing YoY growth %

        Returns:
            CreditCondition: wide, neutral, or tight
        """
        if social_financing_yoy is None:
            logger.debug("Social financing not available, defaulting to neutral credit condition")
            return CreditCondition.NEUTRAL

        if social_financing_yoy > self.SOCIAL_FIN_WIDE:
            condition = CreditCondition.WIDE
        elif social_financing_yoy < self.SOCIAL_FIN_TIGHT:
            condition = CreditCondition.TIGHT
        else:
            condition = CreditCondition.NEUTRAL

        logger.info(f"Credit condition: Social Financing YoY={social_financing_yoy}% -> {condition.value}")
        return condition

    def determine_quadrant(self, monetary: MonetaryCondition,
                          credit: CreditCondition) -> Quadrant:
        """
        Map monetary and credit conditions to quadrant.

        Args:
            monetary: Monetary condition
            credit: Credit condition

        Returns:
            Quadrant: wide-wide, wide-tight, tight-wide, or tight-tight
        """
        quadrant_map = {
            (MonetaryCondition.WIDE, CreditCondition.WIDE): Quadrant.WIDE_WIDE,
            (MonetaryCondition.WIDE, CreditCondition.NEUTRAL): Quadrant.WIDE_WIDE,
            (MonetaryCondition.NEUTRAL, CreditCondition.WIDE): Quadrant.WIDE_WIDE,

            (MonetaryCondition.WIDE, CreditCondition.TIGHT): Quadrant.WIDE_TIGHT,
            (MonetaryCondition.NEUTRAL, CreditCondition.NEUTRAL): Quadrant.WIDE_TIGHT,

            (MonetaryCondition.TIGHT, CreditCondition.WIDE): Quadrant.TIGHT_WIDE,
            (MonetaryCondition.TIGHT, CreditCondition.NEUTRAL): Quadrant.TIGHT_WIDE,

            (MonetaryCondition.TIGHT, CreditCondition.TIGHT): Quadrant.TIGHT_TIGHT,
        }

        quadrant = quadrant_map.get((monetary, credit), Quadrant.WIDE_TIGHT)
        logger.info(f"Quadrant: {monetary.value}-{credit.value} -> {quadrant.value}")
        return quadrant

    def compute_multiplier(self, composite_score: float) -> float:
        """
        Compute macro_multiplier from composite score.

        Formula: multiplier = 1.0 + (composite_score * 0.15)
        Bounds: [0.85, 1.15]

        Examples:
        - composite = +1.0 → multiplier = 1.15 (max risk-on)
        - composite = 0.0  → multiplier = 1.00 (neutral)
        - composite = -1.0 → multiplier = 0.85 (max risk-off)

        Args:
            composite_score: Composite macro score from -1.0 to +1.0

        Returns:
            macro_multiplier in range [0.85, 1.15]
        """
        multiplier = 1.0 + (composite_score * 0.15)
        multiplier = max(self.MULTIPLIER_MIN, min(self.MULTIPLIER_MAX, multiplier))
        multiplier = round(multiplier, 3)

        logger.info(f"Macro multiplier: composite={composite_score:.2f} -> multiplier={multiplier:.3f}")
        return multiplier

    def analyze(self, m2_yoy: Optional[float], social_financing_yoy: Optional[float],
                composite_score: float) -> QuadrantResult:
        """
        Perform full quadrant analysis.

        Args:
            m2_yoy: M2 YoY %
            social_financing_yoy: Social financing YoY %
            composite_score: Composite macro score (-1.0 to +1.0)

        Returns:
            QuadrantResult with all analysis results
        """
        monetary = self.determine_monetary_condition(m2_yoy)
        credit = self.determine_credit_condition(social_financing_yoy)
        quadrant = self.determine_quadrant(monetary, credit)
        multiplier = self.compute_multiplier(composite_score)

        return QuadrantResult(
            monetary_condition=monetary,
            credit_condition=credit,
            quadrant=quadrant,
            macro_multiplier=multiplier
        )
