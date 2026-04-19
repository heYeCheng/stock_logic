"""Stock radar service for individual stock technical and sentiment score calculation.

This module implements pure volume-price analysis for individual stocks,
generating technical and sentiment scores from market data only.

STOCK-05: Stock Market Radar
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.models import StockMarketScore, LeaderRole


# =============================================================================
# Stock Data Class
# =============================================================================


@dataclass
class StockQuoteData:
    """Stock quote data for technical score calculation.

    This is a simple data class that holds volume-price data
    needed for technical calculations.
    """

    ts_code: str
    trade_date: date
    close: Decimal = Decimal("0")
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    pre_close: Decimal = Decimal("0")
    vol: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")

    # Historical data for calculations (oldest first)
    historical_closes: List[Decimal] = field(default_factory=list)
    historical_volumes: List[Decimal] = field(default_factory=list)

    # Limit board status
    is_limit_up: bool = False
    is_limit_down: bool = False
    consecutive_limit_ups: int = 0
    consecutive_gains: int = 0

    # Leader status
    leader_role: Optional[LeaderRole] = None

    # Institutional flow (net buy amount)
    institutional_net_flow: Decimal = Decimal("0")

    @property
    def daily_return(self) -> Decimal:
        """Calculate daily return."""
        if self.pre_close == 0:
            return Decimal("0")
        return (self.close - self.pre_close) / self.pre_close


# =============================================================================
# Technical Score Calculator
# =============================================================================


class StockTechnicalCalculator:
    """Calculate stock technical scores from pure volume-price data.

    Technical indicators:
    - MA alignment: Price vs MA5/MA10/MA20
    - Volume trend: 5-day avg vs 20-day avg
    - RSI: 14-day RSI
    - MACD: Signal line crossover
    """

    def __init__(self):
        """Initialize technical calculator."""
        self.ma_short_period = 5
        self.ma_mid_period = 10
        self.ma_long_period = 20
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def calculate(
        self,
        quotes: List[StockQuoteData],
        snapshot_date: date,
    ) -> Decimal:
        """Calculate technical score from price/volume data.

        Args:
            quotes: Historical quotes (at least 60 days recommended)
            snapshot_date: Score date

        Returns:
            Technical score (0-1)
        """
        if not quotes or len(quotes) < 20:
            return Decimal("0.5")  # Not enough data, neutral

        # Get latest quote
        latest = quotes[-1]

        # MA alignment score (weight: 0.3)
        ma_score = self._ma_alignment_score(quotes)

        # Volume trend score (weight: 0.25)
        volume_score = self._volume_trend_score(quotes)

        # RSI score (weight: 0.25)
        rsi_score = self._rsi_score(quotes)

        # MACD score (weight: 0.2)
        macd_score = self._macd_score(quotes)

        # Weighted average
        total = (
            ma_score * Decimal("0.3")
            + volume_score * Decimal("0.25")
            + rsi_score * Decimal("0.25")
            + macd_score * Decimal("0.2")
        )

        # Clamp to 0-1
        return max(Decimal("0"), min(Decimal("1"), total))

    def _ma_alignment_score(self, quotes: List[StockQuoteData]) -> Decimal:
        """Score based on MA alignment.

        Bullish: price > ma5 > ma10 > ma20
        Bearish: price < ma5 < ma10 < ma20
        """
        if len(quotes) < self.ma_long_period:
            return Decimal("0.5")

        # Calculate moving averages
        ma5 = self._calculate_ma(quotes, self.ma_short_period)
        ma10 = self._calculate_ma(quotes, self.ma_mid_period)
        ma20 = self._calculate_ma(quotes, self.ma_long_period)

        price = quotes[-1].close

        # Bullish alignment: price > ma5 > ma10 > ma20
        if price > ma5 > ma10 > ma20:
            return Decimal("1.0")

        # Bearish alignment: price < ma5 < ma10 < ma20
        if price < ma5 < ma10 < ma20:
            return Decimal("0")

        # Partial alignment - calculate partial score
        score = Decimal("0.5")

        if price > ma5:
            score += Decimal("0.125")
        if ma5 > ma10:
            score += Decimal("0.125")
        if ma10 > ma20:
            score += Decimal("0.125")

        # Price below ma20 but above ma5 = bullish correction
        if ma20 > price > ma5:
            score += Decimal("0.05")

        return min(score, Decimal("1.0"))

    def _volume_trend_score(self, quotes: List[StockQuoteData]) -> Decimal:
        """Score based on volume trend.

        Volume surge (5-day avg > 20-day avg) = high activity
        """
        if len(quotes) < self.ma_long_period:
            return Decimal("0.5")

        vol_5d = sum(q.vol for q in quotes[-self.ma_short_period:]) / self.ma_short_period
        vol_20d = sum(q.vol for q in quotes[-self.ma_long_period:]) / self.ma_long_period

        if vol_20d == 0:
            return Decimal("0.5")

        ratio = vol_5d / vol_20d

        if ratio > Decimal("1.5"):
            return Decimal("1.0")  # Strong volume surge
        elif ratio > Decimal("1.0"):
            return Decimal("0.75")  # Above average
        elif ratio > Decimal("0.8"):
            return Decimal("0.5")  # Normal
        else:
            return Decimal("0.25")  # Low volume

    def _rsi_score(self, quotes: List[StockQuoteData]) -> Decimal:
        """Score based on RSI (14-day).

        RSI > 70 = overbought (strong but caution)
        RSI 50-70 = bullish
        RSI 30-50 = neutral
        RSI < 30 = oversold (weak)
        """
        if len(quotes) < self.rsi_period + 1:
            return Decimal("0.5")

        closes = [q.close for q in quotes]
        rsi = self._calculate_rsi(closes, self.rsi_period)
        rsi_decimal = Decimal(str(rsi))

        if rsi > 70:
            return Decimal("0.8")  # Overbought but strong momentum
        elif rsi > 50:
            return Decimal("0.6")  # Bullish
        elif rsi > 30:
            return Decimal("0.4")  # Neutral
        else:
            return Decimal("0.2")  # Oversold but weak

    def _macd_score(self, quotes: List[StockQuoteData]) -> Decimal:
        """Score based on MACD signal line crossover.

        Bullish: MACD > Signal and MACD > 0
        Bearish: MACD < Signal and MACD < 0
        """
        if len(quotes) < self.macd_slow + self.macd_signal:
            return Decimal("0.5")

        closes = [q.close for q in quotes]
        macd_line, signal_line = self._calculate_macd(closes)

        if macd_line > signal_line and macd_line > 0:
            return Decimal("1.0")  # Bullish crossover above zero
        elif macd_line > signal_line:
            return Decimal("0.75")  # Bullish crossover below zero
        elif macd_line < signal_line and macd_line < 0:
            return Decimal("0")  # Bearish below zero
        else:
            return Decimal("0.25")  # Bearish above zero

    def _calculate_ma(self, quotes: List[StockQuoteData], period: int) -> Decimal:
        """Calculate simple moving average."""
        if len(quotes) < period:
            return Decimal("0")

        return sum(q.close for q in quotes[-period:]) / period

    def _calculate_rsi(self, closes: List[Decimal], period: int) -> float:
        """Calculate RSI from closing prices."""
        if len(closes) < period + 1:
            return 50.0

        # Calculate price changes
        changes = [float(closes[i] - closes[i - 1]) for i in range(1, len(closes))]

        # Separate gains and losses
        gains = [max(0, c) for c in changes[-period:]]
        losses = [max(0, -c) for c in changes[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, closes: List[Decimal]) -> tuple:
        """Calculate MACD line and signal line.

        Returns:
            Tuple of (macd_line, signal_line) as Decimals
        """
        if len(closes) < self.macd_slow + self.macd_signal:
            return (Decimal("0"), Decimal("0"))

        # Calculate EMAs
        ema_fast = self._ema(closes, self.macd_fast)
        ema_slow = self._ema(closes, self.macd_slow)

        macd_line = ema_fast - ema_slow

        # Calculate signal line (EMA of MACD)
        # For simplicity, calculate from MACD line values
        macd_values = []
        for i in range(self.macd_slow, len(closes)):
            fast_ema = self._ema(closes[:i+1], self.macd_fast)
            slow_ema = self._ema(closes[:i+1], self.macd_slow)
            macd_values.append(fast_ema - slow_ema)

        if len(macd_values) >= self.macd_signal:
            signal_line = self._ema_from_values(macd_values, self.macd_signal)
        else:
            signal_line = macd_line

        return (macd_line, signal_line)

    def _ema(self, prices: List[Decimal], period: int) -> Decimal:
        """Calculate exponential moving average from prices."""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else Decimal("0")

        multiplier = Decimal(str(2 / (period + 1)))
        ema = prices[0]

        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _ema_from_values(self, values: List[Decimal], period: int) -> Decimal:
        """Calculate EMA from a list of values (e.g., MACD values)."""
        if len(values) < period:
            return sum(values) / len(values) if values else Decimal("0")

        multiplier = Decimal(str(2 / (period + 1)))
        ema = values[0]

        for value in values[1:]:
            ema = (value - ema) * multiplier + ema

        return ema


# =============================================================================
# Sentiment Score Calculator
# =============================================================================


class StockSentimentCalculator:
    """Calculate stock sentiment scores from market behavior.

    Sentiment indicators:
    - Recent limit-ups: Count in past 5 days
    - Dragon leader status: Is this stock a leader?
    - Institutional buying: Net institutional flow
    """

    def __init__(self):
        """Initialize sentiment calculator."""
        self.limit_up_lookback = 5

    def calculate(
        self,
        stock_code: str,
        snapshot_date: date,
        limit_ups: int,
        is_dragon: bool,
        institutional_flow: Decimal,
    ) -> Decimal:
        """Calculate sentiment score.

        Args:
            stock_code: Stock code
            snapshot_date: Score date
            limit_ups: Count of limit-ups in past 5 days
            is_dragon: Is this stock a dragon leader?
            institutional_flow: Net institutional flow (positive = net buy)

        Returns:
            Sentiment score (0-1)
        """
        # Limit-up frequency score (0-5 scale, weight: 0.4)
        limit_score = min(Decimal(str(limit_ups)) / Decimal("5"), Decimal("1.0"))

        # Dragon leader bonus (weight: 0.35)
        dragon_score = Decimal("1.0") if is_dragon else Decimal("0.5")

        # Institutional flow score (weight: 0.25)
        if institutional_flow > 0:
            # Normalize: 1M+ net buy = 1.0
            flow_score = min(institutional_flow / Decimal("1000000"), Decimal("1.0"))
        else:
            flow_score = Decimal("0")

        # Weighted average
        total = (
            limit_score * Decimal("0.4")
            + dragon_score * Decimal("0.35")
            + flow_score * Decimal("0.25")
        )

        # Clamp to 0-1
        return max(Decimal("0"), min(Decimal("1"), total))


# =============================================================================
# Stock Radar Service
# =============================================================================


class StockRadarService:
    """Generate daily stock market radar snapshots.

    STOCK-05: Combines technical and sentiment scores for each stock.
    """

    def __init__(self):
        """Initialize radar service."""
        self.technical_calc = StockTechnicalCalculator()
        self.sentiment_calc = StockSentimentCalculator()

    async def generate_snapshot(
        self,
        stock_code: str,
        snapshot_date: date,
        quotes: List[StockQuoteData],
        limit_ups: int = 0,
        is_dragon: bool = False,
        institutional_flow: Decimal = Decimal("0"),
        db_session: Optional[AsyncSession] = None,
    ) -> StockMarketScore:
        """Generate market score snapshot for a stock.

        Args:
            stock_code: Stock code (e.g., "000001.SZ")
            snapshot_date: Date of snapshot
            quotes: Historical quote data
            limit_ups: Count of limit-ups in past 5 days
            is_dragon: Whether stock is a dragon leader
            institutional_flow: Net institutional flow
            db_session: Optional database session for persistence

        Returns:
            StockMarketScore object
        """
        # Calculate technical score
        technical = self.technical_calc.calculate(quotes, snapshot_date)

        # Calculate sentiment score
        sentiment = self.sentiment_calc.calculate(
            stock_code, snapshot_date, limit_ups, is_dragon, institutional_flow
        )

        # Composite score (equal weights)
        composite = (technical + sentiment) / Decimal("2")

        # Create score object
        score = StockMarketScore(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            technical_score=technical,
            sentiment_score=sentiment,
            market_composite=composite,
        )

        # Persist if database session provided
        if db_session is not None:
            await self._persist(score, db_session)

        return score

    async def _persist(self, score: StockMarketScore, db_session: AsyncSession) -> None:
        """Persist score to database, handling upsert if exists."""
        # Check if record exists
        stmt = select(StockMarketScore).where(
            StockMarketScore.stock_code == score.stock_code,
            StockMarketScore.snapshot_date == score.snapshot_date,
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.technical_score = score.technical_score
            existing.sentiment_score = score.sentiment_score
            existing.market_composite = score.market_composite
        else:
            # Insert new record
            db_session.add(score)

        await db_session.commit()
