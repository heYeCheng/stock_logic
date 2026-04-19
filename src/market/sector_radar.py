"""Sector radar service for technical and sentiment score calculation.

This module implements pure volume-price analysis for sectors,
completely independent from logic scores.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.models import SectorScore, SectorState
from src.market.structure import StructureMarkerService, StructureMarker
from src.market.concentration import ConcentrationCalculator


# =============================================================================
# Configuration Classes
# =============================================================================


@dataclass
class TechnicalConfig:
    """Configuration for technical score calculation."""

    # MA slope lookback periods
    ma_short_period: int = 20
    ma_long_period: int = 60

    # RSI configuration
    rsi_period: int = 14
    rsi_weight: Decimal = Decimal("0.3")

    # MACD configuration
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_weight: Decimal = Decimal("0.25")

    # Volume configuration
    volume_short: int = 5
    volume_long: int = 20
    volume_weight: Decimal = Decimal("0.25")

    # Trend weight
    trend_weight: Decimal = Decimal("0.2")

    # Volatility (ATR) configuration
    atr_period: int = 14
    atr_weight: Decimal = Decimal("0.0")  # Reserved for future use

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.rsi_weight + self.macd_weight + self.volume_weight + self.trend_weight + self.atr_weight
        if total != Decimal("1.0"):
            raise ValueError(f"Technical weights must sum to 1.0, got {total}")


@dataclass
class SentimentConfig:
    """Configuration for sentiment score calculation."""

    # Limit board weight
    limit_weight: Decimal = Decimal("0.35")

    # Dragon leader weight
    dragon_weight: Decimal = Decimal("0.25")

    # Continuity weight
    continuity_weight: Decimal = Decimal("0.2")

    # Breadth weight
    breadth_weight: Decimal = Decimal("0.2")

    # Consecutive days for continuity
    continuity_lookback: int = 5

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.limit_weight + self.dragon_weight + self.continuity_weight + self.breadth_weight
        if total != Decimal("1.0"):
            raise ValueError(f"Sentiment weights must sum to 1.0, got {total}")


# =============================================================================
# Stock Data Class
# =============================================================================


@dataclass
class StockData:
    """Stock data for score calculation.

    This is a simple data class that holds volume-price data
    needed for technical and sentiment calculations.
    """

    ts_code: str
    name: str
    sector_id: str
    sector_name: str = ""

    # Price data
    close: Decimal = Decimal("0")
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    pre_close: Decimal = Decimal("0")

    # Volume data
    vol: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")

    # Moving averages
    ma20: Optional[Decimal] = None
    ma60: Optional[Decimal] = None

    # Historical prices for calculations (list of closes, oldest first)
    historical_closes: List[Decimal] = field(default_factory=list)
    historical_volumes: List[Decimal] = field(default_factory=list)

    # Limit board data
    is_limit_up: bool = False
    is_limit_down: bool = False
    consecutive_limit_ups: int = 0
    consecutive_gains: int = 0

    # Dragon leader status
    is_dragon_leader: bool = False

    # Market cap rank (for zhongjun identification)
    market_cap_rank: Optional[int] = None

    # Market score (for concentration calculation)
    market_score: Optional[Decimal] = None

    @property
    def daily_return(self) -> Decimal:
        """Calculate daily return."""
        if self.pre_close == 0:
            return Decimal("0")
        return (self.close - self.pre_close) / self.pre_close

    @property
    def above_ma20(self) -> bool:
        """Check if price is above MA20."""
        if self.ma20 is None:
            return False
        return self.close > self.ma20

    @property
    def above_ma60(self) -> bool:
        """Check if price is above MA60."""
        if self.ma60 is None:
            return False
        return self.close > self.ma60


# =============================================================================
# Technical Score Calculator
# =============================================================================


class TechnicalScoreCalculator:
    """Calculate technical scores from volume-price data."""

    def __init__(self, config: Optional[TechnicalConfig] = None):
        self.config = config or TechnicalConfig()

    def calculate(self, stocks: List[StockData], snapshot_date: date) -> Decimal:
        """Calculate technical score for a basket of stocks.

        Components:
        - Trend strength: MA slope (20-day vs 60-day)
        - Momentum: RSI, MACD histogram
        - Volume: 5-day avg vs 20-day avg
        - Volatility: ATR normalized (reserved)

        Args:
            stocks: List of stock data with historical prices
            snapshot_date: Date of snapshot

        Returns:
            Technical score (0-1 scale)
        """
        if not stocks:
            return Decimal("0")

        # Calculate individual component scores for each stock
        trend_scores = [self._ma_slope_score(s) for s in stocks]
        momentum_scores = [self._momentum_score(s) for s in stocks]
        volume_scores = [self._volume_score(s) for s in stocks]

        # Aggregate across all stocks (average)
        avg_trend = self._safe_average(trend_scores)
        avg_momentum = self._safe_average(momentum_scores)
        avg_volume = self._safe_average(volume_scores)

        # Weighted aggregate
        total = (
            avg_trend * self.config.trend_weight
            + avg_momentum * (self.config.rsi_weight + self.config.macd_weight)
            + avg_volume * self.config.volume_weight
        )

        # Clamp to 0-1
        return max(Decimal("0"), min(Decimal("1"), total))

    def _ma_slope_score(self, stock: StockData) -> Decimal:
        """Calculate MA slope score.

        Measures trend strength by comparing MA20 vs MA60.
        Score = 1.0 if MA20 > MA60 (uptrend), 0.0 if MA20 < MA60 (downtrend)
        """
        if stock.ma20 is None or stock.ma60 is None:
            return Decimal("0.5")  # Neutral if no MA data

        # Calculate slope as (MA20 - MA60) / MA60
        if stock.ma60 == 0:
            return Decimal("0.5")

        slope = (stock.ma20 - stock.ma60) / stock.ma60

        # Convert to 0-1 score:
        # slope > 0.1 (strong uptrend) -> 1.0
        # slope < -0.1 (strong downtrend) -> 0.0
        # Linear interpolation in between
        score = Decimal("0.5") + slope * Decimal("5")  # 0.1 slope = 0.5 score change
        return max(Decimal("0"), min(Decimal("1"), score))

    def _momentum_score(self, stock: StockData) -> Decimal:
        """Calculate momentum score from RSI and MACD.

        RSI: 0-30 = oversold (low score), 70-100 = overbought (high score)
        MACD: Positive histogram = bullish (high score)
        """
        rsi_score = self._rsi_score(stock)
        macd_score = self._macd_score(stock)

        # Weighted average of RSI and MACD
        return rsi_score * self.config.rsi_weight + macd_score * self.config.macd_weight

    def _rsi_score(self, stock: StockData) -> Decimal:
        """Calculate RSI score.

        RSI > 50 = bullish (score > 0.5)
        RSI < 50 = bearish (score < 0.5)
        """
        if not stock.historical_closes or len(stock.historical_closes) < self.config.rsi_period:
            return Decimal("0.5")  # Neutral if insufficient data

        rsi = self._calculate_rsi(stock.historical_closes, self.config.rsi_period)

        # Convert RSI (0-100) to score (0-1)
        # RSI 50 = 0.5, RSI 70 = 0.8, RSI 30 = 0.2
        return Decimal(str(rsi)) / Decimal("100")

    def _macd_score(self, stock: StockData) -> Decimal:
        """Calculate MACD histogram score.

        Positive histogram = bullish crossover (high score)
        Negative histogram = bearish (low score)
        """
        if not stock.historical_closes or len(stock.historical_closes) < self.config.macd_slow + self.config.macd_signal:
            return Decimal("0.5")  # Neutral if insufficient data

        macd_histogram = self._calculate_macd_histogram(stock.historical_closes)

        # Convert histogram to 0-1 score
        # Use sigmoid-like function: score = 0.5 + arctan(histogram) / pi
        # Simplified: clamp histogram to -0.1 to 0.1, then linear map
        if macd_histogram > Decimal("0.05"):
            return Decimal("0.8")
        elif macd_histogram < Decimal("-0.05"):
            return Decimal("0.2")
        else:
            return Decimal("0.5") + macd_histogram * Decimal("6")

    def _volume_score(self, stock: StockData) -> Decimal:
        """Calculate volume trend score.

        Volume surge (5-day avg > 20-day avg) = high activity (high score)
        """
        if not stock.historical_volumes or len(stock.historical_volumes) < self.config.volume_long:
            return Decimal("0.5")  # Neutral if insufficient data

        vol_5d = sum(stock.historical_volumes[-5:]) / 5
        vol_20d = sum(stock.historical_volumes[-20:]) / 20

        if vol_20d == 0:
            return Decimal("0.5")

        # Volume ratio
        ratio = Decimal(str(vol_5d / vol_20d))

        # Ratio > 1.5 = high volume (score 0.8)
        # Ratio < 0.5 = low volume (score 0.2)
        if ratio > Decimal("1.5"):
            return Decimal("0.8")
        elif ratio < Decimal("0.5"):
            return Decimal("0.2")
        else:
            # Linear interpolation
            return Decimal("0.2") + (ratio - Decimal("0.5")) * Decimal("0.4")

    def _calculate_rsi(self, closes: List[Decimal], period: int) -> float:
        """Calculate RSI from closing prices."""
        if len(closes) < period + 1:
            return 50.0  # Neutral

        # Calculate price changes
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        # Separate gains and losses
        gains = [max(0, c) for c in changes[-period:]]
        losses = [max(0, -c) for c in changes[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0  # No losses = max RSI

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd_histogram(self, closes: List[Decimal]) -> Decimal:
        """Calculate MACD histogram from closing prices."""
        fast_period = self.config.macd_fast
        slow_period = self.config.macd_slow
        signal_period = self.config.macd_signal

        if len(closes) < slow_period + signal_period:
            return Decimal("0")

        # Calculate EMAs
        ema_fast = self._ema(closes, fast_period)
        ema_slow = self._ema(closes, slow_period)

        macd_line = ema_fast - ema_slow

        # For simplicity, assume signal line is close to MACD line
        # In production, calculate proper signal EMA
        histogram = macd_line * Decimal("0.1")  # Simplified
        return histogram

    def _ema(self, prices: List[Decimal], period: int) -> Decimal:
        """Calculate exponential moving average."""
        if len(prices) < period:
            return Decimal(str(sum(prices) / len(prices))) if prices else Decimal("0")

        multiplier = Decimal(str(2 / (period + 1)))
        ema = Decimal(str(prices[0]))

        for price in prices[1:]:
            ema = (Decimal(str(price)) - ema) * multiplier + ema

        return ema

    def _safe_average(self, values: List[Decimal]) -> Decimal:
        """Calculate average safely, returning 0 for empty list."""
        if not values:
            return Decimal("0")
        return sum(values) / len(values)


# =============================================================================
# Sentiment Score Calculator
# =============================================================================


class SentimentScoreCalculator:
    """Calculate sentiment scores from market behavior."""

    def __init__(self, config: Optional[SentimentConfig] = None):
        self.config = config or SentimentConfig()

    def calculate(self, stocks: List[StockData], snapshot_date: date) -> Decimal:
        """Calculate sentiment score for a basket of stocks.

        Components:
        - Limit board frequency: Count of limit-up stocks
        - Dragon leader presence: Whether sector has a recognized leader
        - Continuity: Consecutive days with positive performance
        - Breadth: % of stocks above MA20

        Args:
            stocks: List of stock data
            snapshot_date: Date of snapshot

        Returns:
            Sentiment score (0-1 scale)
        """
        if not stocks:
            return Decimal("0")

        # Limit board frequency
        limit_score = self._limit_board_score(stocks, snapshot_date)

        # Dragon leader presence
        dragon_score = self._dragon_leader_score(stocks)

        # Continuity
        continuity_score = self._continuity_score(stocks)

        # Breadth
        breadth_score = self._breadth_score(stocks)

        # Weighted aggregate
        total = (
            limit_score * self.config.limit_weight
            + dragon_score * self.config.dragon_weight
            + continuity_score * self.config.continuity_weight
            + breadth_score * self.config.breadth_weight
        )

        # Clamp to 0-1
        return max(Decimal("0"), min(Decimal("1"), total))

    def _limit_board_score(self, stocks: List[StockData], snapshot_date: date) -> Decimal:
        """Calculate limit board frequency score.

        Count of limit-up stocks / total stocks
        """
        if not stocks:
            return Decimal("0")

        limit_up_count = sum(1 for s in stocks if s.is_limit_up)
        ratio = Decimal(str(limit_up_count)) / Decimal(str(len(stocks)))

        # Normalize: 20%+ limit ups = 1.0, 0% = 0.0
        score = ratio * Decimal("5")  # 0.2 ratio = 1.0 score
        return max(Decimal("0"), min(Decimal("1"), score))

    def _dragon_leader_score(self, stocks: List[StockData]) -> Decimal:
        """Calculate dragon leader presence score.

        Returns 1.0 if sector has a dragon leader, 0.5 if has strong follower, 0.0 otherwise.
        """
        if not stocks:
            return Decimal("0")

        # Check for dragon leader
        has_dragon = any(s.is_dragon_leader for s in stocks)
        if has_dragon:
            return Decimal("1.0")

        # Check for potential dragon (consecutive limit ups)
        max_consecutive = max((s.consecutive_limit_ups for s in stocks), default=0)
        if max_consecutive >= 3:
            return Decimal("0.8")
        elif max_consecutive >= 2:
            return Decimal("0.6")
        elif max_consecutive >= 1:
            return Decimal("0.5")

        return Decimal("0.3")  # Base score for any activity

    def _continuity_score(self, stocks: List[StockData]) -> Decimal:
        """Calculate continuity score from consecutive positive days.

        Measures how many stocks have consecutive gains.
        """
        if not stocks:
            return Decimal("0")

        # Average consecutive gains across stocks
        avg_consecutive = sum(s.consecutive_gains for s in stocks) / len(stocks)

        # Normalize: 5+ consecutive = 1.0, 0 = 0.0
        score = Decimal(str(min(avg_consecutive, 5) / 5))
        return score

    def _breadth_score(self, stocks: List[StockData]) -> Decimal:
        """Calculate breadth score.

        % of stocks above MA20
        """
        if not stocks:
            return Decimal("0")

        above_ma20_count = sum(1 for s in stocks if s.above_ma20)
        ratio = Decimal(str(above_ma20_count)) / Decimal(str(len(stocks)))

        return ratio  # Already 0-1


# =============================================================================
# Sector Radar Service
# =============================================================================


class SectorRadarService:
    """Generate daily sector radar snapshots."""

    def __init__(
        self,
        technical_config: Optional[TechnicalConfig] = None,
        sentiment_config: Optional[SentimentConfig] = None,
    ):
        self.technical_calc = TechnicalScoreCalculator(technical_config or TechnicalConfig())
        self.sentiment_calc = SentimentScoreCalculator(sentiment_config or SentimentConfig())
        self.structure_service = StructureMarkerService()
        self.concentration_calc = ConcentrationCalculator()

    async def generate_snapshot(
        self,
        sector_id: str,
        snapshot_date: date,
        stocks: List[StockData],
        db_session: Optional[AsyncSession] = None,
    ) -> SectorScore:
        """Generate snapshot for a sector.

        Args:
            sector_id: Sector identifier
            snapshot_date: Date of snapshot
            stocks: List of stock data in the sector
            db_session: Optional database session for persistence

        Returns:
            SectorScore object
        """
        # Get sector name from first stock
        sector_name = stocks[0].sector_name if stocks else ""

        # Calculate scores
        technical = self.technical_calc.calculate(stocks, snapshot_date)
        sentiment = self.sentiment_calc.calculate(stocks, snapshot_date)
        composite = (technical + sentiment) / Decimal("2")

        # Determine state
        state = self._determine_state(composite)

        # Generate structure marker (MARKET-04)
        structure_marker = await self.structure_service.generate_marker(
            sector_id, snapshot_date, stocks
        )

        # Calculate lead concentration (MARKET-03)
        concentration = self.concentration_calc.calculate(stocks)
        concentration_interpretation = self.concentration_calc.interpret(concentration)

        # Create score object
        score = SectorScore(
            sector_id=sector_id,
            sector_name=sector_name,
            snapshot_date=snapshot_date,
            technical_score=technical,
            sentiment_score=sentiment,
            composite_score=composite,
            state=state,
            lead_concentration=concentration,
            concentration_interpretation=concentration_interpretation,
            structure_marker=structure_marker.marker,
            structure_confidence=structure_marker.confidence,
        )

        # Persist if database session provided
        if db_session is not None:
            await self._persist(score, db_session)

        return score

    def _determine_state(self, composite: Decimal) -> SectorState:
        """Determine sector state from composite score.

        Thresholds:
        - weak: composite_score < 0.35
        - normal: 0.35 <= composite_score <= 0.70
        - overheated: composite_score > 0.70
        """
        if composite < Decimal("0.35"):
            return SectorState.weak
        elif composite > Decimal("0.70"):
            return SectorState.overheated
        else:
            return SectorState.normal

    async def _persist(self, score: SectorScore, db_session: AsyncSession) -> None:
        """Persist score to database."""
        db_session.add(score)
        await db_session.commit()

    async def _get_sector_stocks(self, sector_id: str, snapshot_date: date) -> List[StockData]:
        """Get sector constituent stocks.

        This is a placeholder - in production, this would query
        the stock-sector mapping table.
        """
        # Placeholder implementation
        # In production: query stock_sector_mappings and daily quotes
        return []
