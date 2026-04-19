"""Macro scorer - scores macro dimensions from -1.0 to +1.0."""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class MacroScorer:
    """Score macro dimensions from -1.0 to +1.0 using configurable thresholds."""

    # Configurable thresholds for liquidity (M2 YoY)
    LIQUIDITY_WIDE = 10.0  # M2 YoY > 10% = +1
    LIQUIDITY_TIGHT = 8.0  # M2 YoY < 8% = -1

    # Configurable thresholds for growth (PMI)
    GROWTH_STRONG = 52.0  # PMI > 52 = +1
    GROWTH_WEAK = 48.0  # PMI < 48 = -1

    # Configurable thresholds for inflation (CPI YoY)
    # Note: Moderate inflation (2-3%) is healthy, deflation or high inflation is bad
    INFLATION_OPTIMAL_LOW = 2.0  # CPI >= 2% = +0.5
    INFLATION_OPTIMAL_HIGH = 3.0  # CPI <= 3% = +0.5
    INFLATION_HIGH = 5.0  # CPI > 5% = -1 (high inflation)
    INFLATION_DEFLATION = 0.0  # CPI < 0% = -1 (deflation)

    # Configurable thresholds for global (DXY - lower is better for EM)
    GLOBAL_DXY_LOW = 95.0  # DXY < 95 = +0.5 (weak dollar, good for EM)
    GLOBAL_DXY_HIGH = 110.0  # DXY > 110 = -0.5 (strong dollar, bad for EM)

    def score_liquidity(self, m2_yoy: Optional[float], dr007: Optional[float] = None,
                        bond_yield: Optional[float] = None) -> float:
        """
        Score liquidity dimension based on M2 YoY.

        Args:
            m2_yoy: M2 money supply YoY growth %
            dr007: DR007 interbank rate (optional)
            bond_yield: 10Y bond yield (optional)

        Returns:
            Score from -1.0 to +1.0
        """
        if m2_yoy is None:
            logger.debug("M2 YoY not available, returning neutral liquidity score")
            return 0.0

        # Linear interpolation between thresholds
        if m2_yoy >= self.LIQUIDITY_WIDE:
            score = 1.0
        elif m2_yoy <= self.LIQUIDITY_TIGHT:
            score = -1.0
        else:
            # Linear interpolation: map [8, 10] to [-1, 1]
            score = (m2_yoy - self.LIQUIDITY_TIGHT) / (self.LIQUIDITY_WIDE - self.LIQUIDITY_TIGHT) * 2 - 1

        logger.debug(f"Liquidity score: M2 YoY={m2_yoy}% -> score={score:.2f}")
        return round(score, 2)

    def score_growth(self, pmi: Optional[float], gdp_yoy: Optional[float] = None,
                     industrial_prod: Optional[float] = None) -> float:
        """
        Score growth dimension based on PMI.

        Args:
            pmi: Manufacturing PMI
            gdp_yoy: GDP YoY (optional)
            industrial_prod: Industrial production YoY (optional)

        Returns:
            Score from -1.0 to +1.0
        """
        if pmi is None:
            logger.debug("PMI not available, returning neutral growth score")
            return 0.0

        # PMI: 50 is expansion/contraction boundary
        if pmi >= self.GROWTH_STRONG:
            score = 1.0
        elif pmi <= self.GROWTH_WEAK:
            score = -1.0
        else:
            # Linear interpolation around 50
            score = (pmi - 50) / 2  # Map [48, 52] to [-1, 1]

        logger.debug(f"Growth score: PMI={pmi} -> score={score:.2f}")
        return round(score, 2)

    def score_inflation(self, cpi_yoy: Optional[float], ppi_yoy: Optional[float] = None) -> float:
        """
        Score inflation dimension based on CPI YoY.

        Moderate inflation (2-3%) is healthy (+0.5).
        Deflation (<0%) or high inflation (>5%) is negative (-1).

        Args:
            cpi_yoy: CPI YoY %
            ppi_yoy: PPI YoY (optional)

        Returns:
            Score from -1.0 to +1.0
        """
        if cpi_yoy is None:
            logger.debug("CPI not available, returning neutral inflation score")
            return 0.0

        # Optimal range: 2-3%
        if self.INFLATION_OPTIMAL_LOW <= cpi_yoy <= self.INFLATION_OPTIMAL_HIGH:
            score = 0.5
        elif cpi_yoy < self.INFLATION_DEFLATION:
            # Deflation is bad
            score = -1.0
        elif cpi_yoy > self.INFLATION_HIGH:
            # High inflation is bad
            score = -1.0
        elif cpi_yoy < self.INFLATION_OPTIMAL_LOW:
            # Below optimal but not deflation: linear from -0.5 to 0.5
            score = (cpi_yoy / self.INFLATION_OPTIMAL_LOW) * 0.5 - 0.5
        else:
            # Above optimal but not high: linear from 0.5 to -1
            score = 0.5 - (cpi_yoy - self.INFLATION_OPTIMAL_HIGH) / (self.INFLATION_HIGH - self.INFLATION_OPTIMAL_HIGH) * 1.5

        logger.debug(f"Inflation score: CPI={cpi_yoy}% -> score={score:.2f}")
        return round(score, 2)

    def score_policy(self, policy_score: Optional[float] = None) -> float:
        """
        Score policy dimension.

        Phase 2: Simplified - returns neutral or based on data availability
        Phase 3+: Will incorporate NLP on policy statements

        Args:
            policy_score: Pre-computed policy score (optional)

        Returns:
            Score from -1.0 to +1.0
        """
        if policy_score is not None:
            return policy_score
        # Phase 2: Neutral policy score
        return 0.0

    def score_global(self, fed_rate: Optional[float] = None, dxy: Optional[float] = None,
                     us_cn_spread: Optional[float] = None) -> float:
        """
        Score global dimension based on DXY and Fed rate.

        Lower DXY (weak dollar) is generally better for EM like China.
        Lower Fed rate is generally better for EM capital flows.

        Args:
            fed_rate: Fed funds rate %
            dxy: Dollar Index
            us_cn_spread: US-CN 10Y spread %

        Returns:
            Score from -1.0 to +1.0
        """
        score = 0.0

        # DXY component
        if dxy is not None:
            if dxy <= self.GLOBAL_DXY_LOW:
                score += 0.5
            elif dxy >= self.GLOBAL_DXY_HIGH:
                score -= 0.5
            else:
                # Linear interpolation
                score += 0.5 - (dxy - self.GLOBAL_DXY_LOW) / (self.GLOBAL_DXY_HIGH - self.GLOBAL_DXY_LOW)

        # Fed rate component (simplified)
        if fed_rate is not None:
            if fed_rate <= 3.0:
                score += 0.25
            elif fed_rate >= 5.0:
                score -= 0.25

        logger.debug(f"Global score: DXY={dxy}, Fed={fed_rate} -> score={score:.2f}")
        return round(score, 2)

    def score_all(self, indicators: Dict[str, Optional[Any]]) -> Dict[str, float]:
        """
        Score all five dimensions from indicators.

        Args:
            indicators: dict from MacroFetcher

        Returns:
            dict with liquidity_score, growth_score, inflation_score, policy_score, global_score, composite_score
        """
        liquidity_score = self.score_liquidity(
            indicators.get("m2_yoy"),
            indicators.get("dr007_avg"),
            indicators.get("bond_10y_yield")
        )

        growth_score = self.score_growth(
            indicators.get("pmi_manufacturing"),
            indicators.get("gdp_yoy"),
            indicators.get("industrial_prod_yoy")
        )

        inflation_score = self.score_inflation(
            indicators.get("cpi_yoy"),
            indicators.get("ppi_yoy")
        )

        policy_score = self.score_policy(indicators.get("policy_score"))

        global_score = self.score_global(
            indicators.get("fed_rate"),
            indicators.get("dxy_index"),
            indicators.get("us_cn_spread")
        )

        # Composite: equal weight (0.2) for each dimension
        composite_score = (liquidity_score + growth_score + inflation_score + policy_score + global_score) / 5

        result = {
            "liquidity_score": liquidity_score,
            "growth_score": growth_score,
            "inflation_score": inflation_score,
            "policy_score": policy_score,
            "global_score": global_score,
            "composite_score": round(composite_score, 2)
        }

        logger.info(f"Macro scores computed: composite={composite_score:.2f}")
        logger.debug(f"  Liquidity: {liquidity_score:.2f}, Growth: {growth_score:.2f}, Inflation: {inflation_score:.2f}, Policy: {policy_score:.2f}, Global: {global_score:.2f}")

        return result
