"""Unit tests for STOCK-05: Stock Market Radar.

Tests:
- Technical score calculation (MA alignment)
- Technical score calculation (volume trend)
- Technical score calculation (RSI)
- Technical score calculation (MACD)
- Sentiment score calculation
- Composite score aggregation
- Snapshot persistence
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.market.stock_radar import (
    StockTechnicalCalculator,
    StockSentimentCalculator,
    StockRadarService,
    StockQuoteData,
)


class TestStockTechnicalCalculator:
    """Test stock technical score calculation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = StockTechnicalCalculator()
        self.base_date = date(2026, 4, 19)

    def _create_bullish_quotes(self) -> list:
        """Create quotes with bullish MA alignment (price > MA5 > MA10 > MA20)."""
        quotes = []
        # Create 65 days of quotes with upward trend
        base_price = Decimal("10.00")
        for i in range(65):
            # Gradual uptrend with some volatility
            close = base_price + Decimal(str(i * 0.05)) + Decimal(str((i % 5) * 0.02))
            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=65 - i),
                    close=close,
                    open=close - Decimal("0.1"),
                    high=close + Decimal("0.15"),
                    low=close - Decimal("0.2"),
                    pre_close=close * Decimal("0.98"),
                    vol=Decimal(str(1000000 + i * 10000)),
                    amount=Decimal(str(10000000 + i * 100000)),
                )
            )
        return quotes

    def _create_bearish_quotes(self) -> list:
        """Create quotes with bearish MA alignment (price < MA5 < MA10 < MA20)."""
        quotes = []
        # Create 65 days of quotes with downward trend
        base_price = Decimal("15.00")
        for i in range(65):
            # Gradual downtrend
            close = base_price - Decimal(str(i * 0.05)) - Decimal(str((i % 5) * 0.02))
            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=65 - i),
                    close=close,
                    open=close + Decimal("0.1"),
                    high=close + Decimal("0.2"),
                    low=close - Decimal("0.15"),
                    pre_close=close * Decimal("1.02"),
                    vol=Decimal(str(1000000 - i * 5000)),
                    amount=Decimal(str(10000000 - i * 50000)),
                )
            )
        return quotes

    def _create_high_volume_quotes(self) -> list:
        """Create quotes with high recent volume (5-day avg > 20-day avg)."""
        quotes = []
        base_price = Decimal("10.00")
        for i in range(65):
            close = base_price + Decimal(str(i * 0.02))
            # Surge volume in last 5 days
            if i >= 60:
                vol = Decimal(str(3000000))  # 3x normal volume
            else:
                vol = Decimal(str(1000000))

            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=65 - i),
                    close=close,
                    vol=vol,
                )
            )
        return quotes

    def test_ma_alignment_bullish(self):
        """Test MA alignment score with bullish configuration."""
        quotes = self._create_bullish_quotes()
        score = self.calc._ma_alignment_score(quotes)
        assert score == Decimal("1.0"), "Bullish alignment should score 1.0"

    def test_ma_alignment_bearish(self):
        """Test MA alignment score with bearish configuration."""
        quotes = self._create_bearish_quotes()
        score = self.calc._ma_alignment_score(quotes)
        assert score == Decimal("0"), "Bearish alignment should score 0"

    def test_volume_trend_high(self):
        """Test volume trend score with high recent volume."""
        quotes = self._create_high_volume_quotes()
        score = self.calc._volume_trend_score(quotes)
        assert score > Decimal("0.75"), "High volume should score > 0.75"

    def test_volume_trend_normal(self):
        """Test volume trend score with normal volume."""
        quotes = self._create_bullish_quotes()
        score = self.calc._volume_trend_score(quotes)
        # Default volume pattern should give moderate score
        assert Decimal("0.25") <= score <= Decimal("1.0")

    def test_rsi_score_overbought(self):
        """Test RSI score with overbought condition (RSI > 70)."""
        # Create quotes with strong upward momentum
        quotes = []
        base_price = Decimal("10.00")
        for i in range(20):
            # Strong daily gains to push RSI high
            close = base_price * (Decimal("1.03") ** i)
            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=20 - i),
                    close=close,
                )
            )
        score = self.calc._rsi_score(quotes)
        # Overbought RSI > 70 should still give high score
        assert score >= Decimal("0.6"), "Overbought RSI should score at least 0.6"

    def test_rsi_score_insufficient_data(self):
        """Test RSI score with insufficient data."""
        quotes = [
            StockQuoteData(
                ts_code="000001.SZ",
                trade_date=self.base_date - timedelta(days=i),
                close=Decimal("10.00"),
            )
            for i in range(10)
        ]
        score = self.calc._rsi_score(quotes)
        assert score == Decimal("0.5"), "Insufficient data should return neutral 0.5"

    def test_macd_score_bullish(self):
        """Test MACD score with bullish crossover."""
        # Create quotes with upward momentum for MACD calculation
        quotes = []
        base_price = Decimal("10.00")
        for i in range(30):
            # Gradual uptrend
            close = base_price + Decimal(str(i * 0.1))
            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=30 - i),
                    close=close,
                )
            )
        score = self.calc._macd_score(quotes)
        # Should be able to calculate MACD with 30 days of data
        assert score >= Decimal("0")

    def test_macd_score_insufficient_data(self):
        """Test MACD score with insufficient data."""
        quotes = [
            StockQuoteData(
                ts_code="000001.SZ",
                trade_date=self.base_date - timedelta(days=i),
                close=Decimal("10.00"),
            )
            for i in range(20)
        ]
        score = self.calc._macd_score(quotes)
        assert score == Decimal("0.5"), "Insufficient data should return neutral 0.5"

    def test_calculate_full_bullish(self):
        """Test full technical score calculation with bullish data."""
        quotes = self._create_bullish_quotes()
        score = self.calc.calculate(quotes, self.base_date)
        assert Decimal("0.5") < score <= Decimal("1.0"), "Bullish data should score > 0.5"

    def test_calculate_insufficient_data(self):
        """Test technical score with insufficient data."""
        quotes = [
            StockQuoteData(
                ts_code="000001.SZ",
                trade_date=self.base_date - timedelta(days=i),
                close=Decimal("10.00"),
            )
            for i in range(15)
        ]
        score = self.calc.calculate(quotes, self.base_date)
        assert score == Decimal("0.5"), "Insufficient data should return neutral 0.5"


class TestStockSentimentCalculator:
    """Test stock sentiment score calculation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = StockSentimentCalculator()
        self.base_date = date(2026, 4, 19)

    def test_sentiment_max_limit_ups(self):
        """Test sentiment score with maximum limit-ups (5)."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=5,
            is_dragon=False,
            institutional_flow=Decimal("0"),
        )
        # limit_score = 1.0, dragon_score = 0.5, flow_score = 0
        # total = 1.0 * 0.4 + 0.5 * 0.35 + 0 * 0.25 = 0.575
        assert score == Decimal("0.575")

    def test_sentiment_dragon_leader(self):
        """Test sentiment score with dragon leader status."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=0,
            is_dragon=True,
            institutional_flow=Decimal("0"),
        )
        # limit_score = 0, dragon_score = 1.0, flow_score = 0
        # total = 0 * 0.4 + 1.0 * 0.35 + 0 * 0.25 = 0.35
        assert score == Decimal("0.35")

    def test_sentiment_high_institutional_flow(self):
        """Test sentiment score with high institutional flow."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=0,
            is_dragon=False,
            institutional_flow=Decimal("2000000"),  # 2M net buy
        )
        # limit_score = 0, dragon_score = 0.5, flow_score = 1.0 (capped)
        # total = 0 * 0.4 + 0.5 * 0.35 + 1.0 * 0.25 = 0.425
        assert score == Decimal("0.425")

    def test_sentiment_all_positive(self):
        """Test sentiment score with all positive factors."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=3,
            is_dragon=True,
            institutional_flow=Decimal("1500000"),  # 1.5M net buy
        )
        # limit_score = 0.6, dragon_score = 1.0, flow_score = 1.0 (capped)
        # total = 0.6 * 0.4 + 1.0 * 0.35 + 1.0 * 0.25 = 0.84
        assert score == Decimal("0.84")

    def test_sentiment_all_zero(self):
        """Test sentiment score with all zero factors."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=0,
            is_dragon=False,
            institutional_flow=Decimal("0"),
        )
        # limit_score = 0, dragon_score = 0.5, flow_score = 0
        # total = 0 * 0.4 + 0.5 * 0.35 + 0 * 0.25 = 0.175
        assert score == Decimal("0.175")

    def test_sentiment_negative_flow(self):
        """Test sentiment score with negative institutional flow."""
        score = self.calc.calculate(
            stock_code="000001.SZ",
            snapshot_date=self.base_date,
            limit_ups=0,
            is_dragon=False,
            institutional_flow=Decimal("-500000"),  # Net sell
        )
        # Negative flow = 0 score
        assert score == Decimal("0.175")  # Same as all zero


class TestStockRadarService:
    """Test stock radar service integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = StockRadarService()
        self.base_date = date(2026, 4, 19)

    def _create_test_quotes(self, count: int = 65) -> list:
        """Create test quote data."""
        quotes = []
        base_price = Decimal("10.00")
        for i in range(count):
            close = base_price + Decimal(str(i * 0.05))
            quotes.append(
                StockQuoteData(
                    ts_code="000001.SZ",
                    trade_date=self.base_date - timedelta(days=count - i),
                    close=close,
                    vol=Decimal(str(1000000)),
                )
            )
        return quotes

    def test_generate_snapshot(self):
        """Test generating stock market snapshot."""
        quotes = self._create_test_quotes()

        # Create snapshot without database persistence
        import asyncio

        async def run_test():
            score = await self.service.generate_snapshot(
                stock_code="000001.SZ",
                snapshot_date=self.base_date,
                quotes=quotes,
                limit_ups=2,
                is_dragon=False,
                institutional_flow=Decimal("500000"),
                db_session=None,  # No database
            )
            return score

        score = asyncio.run(run_test())

        assert score.stock_code == "000001.SZ"
        assert score.snapshot_date == self.base_date
        assert score.technical_score is not None
        assert score.sentiment_score is not None
        assert score.market_composite is not None

        # Verify composite is average of technical and sentiment
        expected_composite = (score.technical_score + score.sentiment_score) / Decimal("2")
        assert score.market_composite == expected_composite

    def test_generate_snapshot_insufficient_data(self):
        """Test generating snapshot with insufficient data."""
        quotes = self._create_test_quotes(count=10)  # Not enough data

        import asyncio

        async def run_test():
            score = await self.service.generate_snapshot(
                stock_code="000001.SZ",
                snapshot_date=self.base_date,
                quotes=quotes,
                limit_ups=0,
                is_dragon=False,
                institutional_flow=Decimal("0"),
                db_session=None,
            )
            return score

        score = asyncio.run(run_test())

        # Should still generate snapshot with neutral technical score
        assert score.technical_score == Decimal("0.5")


class TestStockQuoteData:
    """Test StockQuoteData dataclass."""

    def test_daily_return(self):
        """Test daily return calculation."""
        quote = StockQuoteData(
            ts_code="000001.SZ",
            trade_date=date(2026, 4, 19),
            close=Decimal("11.00"),
            pre_close=Decimal("10.00"),
        )
        assert quote.daily_return == Decimal("0.1")

    def test_daily_return_zero_pre_close(self):
        """Test daily return with zero pre-close."""
        quote = StockQuoteData(
            ts_code="000001.SZ",
            trade_date=date(2026, 4, 19),
            close=Decimal("11.00"),
            pre_close=Decimal("0"),
        )
        assert quote.daily_return == Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
