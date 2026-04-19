"""Unit tests for sector radar module.

Tests:
- Technical score calculation (individual components)
- Sentiment score calculation (individual components)
- Composite score aggregation
- State determination (weak/normal/overheated)
- Sector snapshot persistence
- Empty sector handling
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.market.sector_radar import (
    TechnicalScoreCalculator,
    SentimentScoreCalculator,
    SectorRadarService,
    TechnicalConfig,
    SentimentConfig,
    StockData,
)
from src.market.models import SectorScore, SectorState


class TestTechnicalConfig:
    """Test technical configuration."""

    def test_default_config_weights_sum_to_one(self):
        """Test default configuration weights sum to 1.0."""
        config = TechnicalConfig()
        total = (
            config.trend_weight
            + config.rsi_weight
            + config.macd_weight
            + config.volume_weight
            + config.atr_weight
        )
        assert total == Decimal("1.0")

    def test_invalid_weights_raises_error(self):
        """Test that invalid weights raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            TechnicalConfig(
                rsi_weight=Decimal("0.5"),
                macd_weight=Decimal("0.5"),
                volume_weight=Decimal("0.5"),
                trend_weight=Decimal("0.5"),
                atr_weight=Decimal("0.0"),
            )


class TestSentimentConfig:
    """Test sentiment configuration."""

    def test_default_config_weights_sum_to_one(self):
        """Test default configuration weights sum to 1.0."""
        config = SentimentConfig()
        total = (
            config.limit_weight
            + config.dragon_weight
            + config.continuity_weight
            + config.breadth_weight
        )
        assert total == Decimal("1.0")

    def test_invalid_weights_raises_error(self):
        """Test that invalid weights raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            SentimentConfig(
                limit_weight=Decimal("0.5"),
                dragon_weight=Decimal("0.5"),
                continuity_weight=Decimal("0.5"),
                breadth_weight=Decimal("0.5"),
            )


class TestStockData:
    """Test StockData data class."""

    def test_daily_return_calculation(self):
        """Test daily return calculation."""
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("110"),
            pre_close=Decimal("100"),
        )
        assert stock.daily_return == Decimal("0.1")

    def test_daily_return_zero_pre_close(self):
        """Test daily return when pre_close is zero."""
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("110"),
            pre_close=Decimal("0"),
        )
        assert stock.daily_return == Decimal("0")

    def test_above_ma20_true(self):
        """Test above_ma20 property when price is above MA20."""
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("110"),
            ma20=Decimal("100"),
        )
        assert stock.above_ma20 is True

    def test_above_ma20_false(self):
        """Test above_ma20 property when price is below MA20."""
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("90"),
            ma20=Decimal("100"),
        )
        assert stock.above_ma20 is False

    def test_above_ma20_no_data(self):
        """Test above_ma20 property when MA20 is None."""
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("110"),
        )
        assert stock.above_ma20 is False


class TestTechnicalScoreCalculator:
    """Test technical score calculation."""

    def test_empty_stocks_returns_zero(self):
        """Test that empty stock list returns zero score."""
        calc = TechnicalScoreCalculator()
        score = calc.calculate([], date.today())
        assert score == Decimal("0")

    def test_neutral_stock_returns_mid_range_score(self):
        """Test stock with no historical data returns mid-range score."""
        calc = TechnicalScoreCalculator()
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("100"),
        )
        score = calc.calculate([stock], date.today())
        # With no historical data:
        # - trend (MA slope): 0.5 (no MA data)
        # - momentum (RSI/MACD): RSI returns 0.5, MACD returns 0.5, but weighted by config
        # - volume: 0.5 (no volume data)
        # Score is approximately 0.5, allow some tolerance
        assert Decimal("0.3") < score < Decimal("0.7")

    def test_ma_slope_score_uptrend(self):
        """Test MA slope score for uptrend (MA20 > MA60)."""
        calc = TechnicalScoreCalculator()
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("110"),
            ma20=Decimal("105"),
            ma60=Decimal("100"),
        )
        score = calc._ma_slope_score(stock)
        # Slope = (105-100)/100 = 0.05
        # Score = 0.5 + 0.05 * 5 = 0.75
        assert score == Decimal("0.75")

    def test_ma_slope_score_downtrend(self):
        """Test MA slope score for downtrend (MA20 < MA60)."""
        calc = TechnicalScoreCalculator()
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("90"),
            ma20=Decimal("95"),
            ma60=Decimal("100"),
        )
        score = calc._ma_slope_score(stock)
        # Slope = (95-100)/100 = -0.05
        # Score = 0.5 + (-0.05) * 5 = 0.25
        assert score == Decimal("0.25")

    def test_ma_slope_score_no_ma_data(self):
        """Test MA slope score when MA data is missing."""
        calc = TechnicalScoreCalculator()
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
        )
        score = calc._ma_slope_score(stock)
        assert score == Decimal("0.5")  # Neutral

    def test_volume_score_high_volume(self):
        """Test volume score with high volume (5-day > 20-day)."""
        calc = TechnicalScoreCalculator()
        # Create stock with 20 days of volume data
        volumes = [Decimal("1000")] * 15 + [Decimal("2000")] * 5  # Recent 5 days higher
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            historical_volumes=volumes,
        )
        score = calc._volume_score(stock)
        # 5-day avg = 2000, 20-day avg = 1250
        # Ratio = 2000/1250 = 1.6 > 1.5, so score = 0.8
        assert score == Decimal("0.8")

    def test_volume_score_low_volume(self):
        """Test volume score with low volume (5-day < 20-day)."""
        calc = TechnicalScoreCalculator()
        # Create stock with 20 days of volume data
        volumes = [Decimal("2000")] * 15 + [Decimal("500")] * 5  # Recent 5 days lower
        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            historical_volumes=volumes,
        )
        score = calc._volume_score(stock)
        # 5-day avg = 500, 20-day avg = 1625
        # Ratio = 500/1625 ≈ 0.31 < 0.5, so score = 0.2
        assert score == Decimal("0.2")

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        calc = TechnicalScoreCalculator()
        # Create 15 days of prices with upward trend
        closes = [Decimal("100"), Decimal("102"), Decimal("104"), Decimal("106"), Decimal("108"),
                  Decimal("110"), Decimal("112"), Decimal("114"), Decimal("116"), Decimal("118"),
                  Decimal("120"), Decimal("122"), Decimal("124"), Decimal("126"), Decimal("128")]
        rsi = calc._calculate_rsi(closes, 14)
        # With consistent gains, RSI should be 100 (no losses)
        assert rsi == 100.0

    def test_rsi_mixed_prices(self):
        """Test RSI with mixed price movements."""
        calc = TechnicalScoreCalculator()
        # Alternating prices
        closes = [Decimal("100"), Decimal("105"), Decimal("95"), Decimal("105"), Decimal("95"),
                  Decimal("105"), Decimal("95"), Decimal("105"), Decimal("95"), Decimal("105"),
                  Decimal("95"), Decimal("105"), Decimal("95"), Decimal("105"), Decimal("95")]
        rsi = calc._calculate_rsi(closes, 14)
        # Equal gains and losses, RSI should be approximately 50
        assert 45.0 < rsi < 55.0

    def test_calculate_with_full_data(self):
        """Test technical score calculation with complete data."""
        calc = TechnicalScoreCalculator()

        # Create stock with uptrend, high volume
        volumes = [Decimal("1000")] * 20 + [Decimal("2000")] * 5
        closes = [Decimal("100")] + [Decimal("100") + Decimal(str(i)) for i in range(1, 30)]

        stock = StockData(
            ts_code="000001.SZ",
            name="Test Stock",
            sector_id="sector_test",
            close=Decimal("130"),
            ma20=Decimal("120"),
            ma60=Decimal("110"),
            historical_volumes=volumes,
            historical_closes=closes,
        )

        score = calc.calculate([stock], date.today())
        # Should be > 0.5 due to uptrend and high volume
        assert score > Decimal("0.5")


class TestSentimentScoreCalculator:
    """Test sentiment score calculation."""

    def test_empty_stocks_returns_zero(self):
        """Test that empty stock list returns zero score."""
        calc = SentimentScoreCalculator()
        score = calc.calculate([], date.today())
        assert score == Decimal("0")

    def test_limit_board_score_all_limit_up(self):
        """Test limit board score when all stocks are limit up."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code=f"00000{i}.SZ", name=f"Stock {i}", sector_id="test", is_limit_up=True)
            for i in range(5)
        ]
        score = calc._limit_board_score(stocks, date.today())
        # 100% limit ups, ratio = 1.0, score = 1.0 * 5 = 5.0, clamped to 1.0
        assert score == Decimal("1.0")

    def test_limit_board_score_partial_limit_up(self):
        """Test limit board score with partial limit ups."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Stock 1", sector_id="test", is_limit_up=True),
            StockData(ts_code="000002.SZ", name="Stock 2", sector_id="test", is_limit_up=False),
            StockData(ts_code="000003.SZ", name="Stock 3", sector_id="test", is_limit_up=False),
            StockData(ts_code="000004.SZ", name="Stock 4", sector_id="test", is_limit_up=False),
            StockData(ts_code="000005.SZ", name="Stock 5", sector_id="test", is_limit_up=False),
        ]
        score = calc._limit_board_score(stocks, date.today())
        # 1/5 = 20% limit ups, ratio = 0.2, score = 0.2 * 5 = 1.0
        assert score == Decimal("1.0")

    def test_dragon_leader_score_with_dragon(self):
        """Test dragon leader score when dragon is present."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Dragon", sector_id="test", is_dragon_leader=True),
            StockData(ts_code="000002.SZ", name="Follower", sector_id="test"),
        ]
        score = calc._dragon_leader_score(stocks)
        assert score == Decimal("1.0")

    def test_dragon_leader_score_with_consecutive_limit_ups(self):
        """Test dragon leader score with consecutive limit ups."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Hot Stock", sector_id="test", consecutive_limit_ups=3),
            StockData(ts_code="000002.SZ", name="Follower", sector_id="test"),
        ]
        score = calc._dragon_leader_score(stocks)
        assert score == Decimal("0.8")

    def test_dragon_leader_score_no_leader(self):
        """Test dragon leader score with no leader."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Stock 1", sector_id="test"),
            StockData(ts_code="000002.SZ", name="Stock 2", sector_id="test"),
        ]
        score = calc._dragon_leader_score(stocks)
        assert score == Decimal("0.3")  # Base score

    def test_continuity_score(self):
        """Test continuity score from consecutive gains."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Stock 1", sector_id="test", consecutive_gains=5),
            StockData(ts_code="000002.SZ", name="Stock 2", sector_id="test", consecutive_gains=3),
            StockData(ts_code="000003.SZ", name="Stock 3", sector_id="test", consecutive_gains=2),
        ]
        score = calc._continuity_score(stocks)
        # Average = (5+3+2)/3 = 3.33, normalized = 3.33/5 = 0.666...
        # Allow for floating point precision
        assert abs(score - Decimal("2") / Decimal("3")) < Decimal("0.001")

    def test_breadth_score(self):
        """Test breadth score (% above MA20)."""
        calc = SentimentScoreCalculator()
        stocks = [
            StockData(ts_code="000001.SZ", name="Stock 1", sector_id="test", close=Decimal("110"), ma20=Decimal("100")),
            StockData(ts_code="000002.SZ", name="Stock 2", sector_id="test", close=Decimal("110"), ma20=Decimal("100")),
            StockData(ts_code="000003.SZ", name="Stock 3", sector_id="test", close=Decimal("90"), ma20=Decimal("100")),
            StockData(ts_code="000004.SZ", name="Stock 4", sector_id="test", close=Decimal("90"), ma20=Decimal("100")),
            StockData(ts_code="000005.SZ", name="Stock 5", sector_id="test", close=Decimal("110"), ma20=Decimal("100")),
        ]
        score = calc._breadth_score(stocks)
        # 3/5 = 60% above MA20
        assert score == Decimal("0.6")

    def test_full_sentiment_calculation(self):
        """Test complete sentiment score calculation."""
        calc = SentimentScoreCalculator()

        # Create stocks with positive sentiment
        stocks = [
            StockData(
                ts_code="000001.SZ",
                name="Dragon",
                sector_id="test",
                is_limit_up=True,
                is_dragon_leader=True,
                consecutive_gains=3,
                close=Decimal("110"),
                ma20=Decimal("100"),
            ),
            StockData(
                ts_code="000002.SZ",
                name="Follower 1",
                sector_id="test",
                is_limit_up=True,
                consecutive_gains=2,
                close=Decimal("105"),
                ma20=Decimal("100"),
            ),
            StockData(
                ts_code="000003.SZ",
                name="Follower 2",
                sector_id="test",
                consecutive_gains=1,
                close=Decimal("95"),
                ma20=Decimal("100"),
            ),
        ]

        score = calc.calculate(stocks, date.today())
        # Should be > 0.5 due to positive sentiment indicators
        assert score > Decimal("0.5")


class TestSectorRadarService:
    """Test sector radar service."""

    def test_service_initialization(self):
        """Test service initializes correctly."""
        service = SectorRadarService()
        assert service.technical_calc is not None
        assert service.sentiment_calc is not None

    def test_generate_snapshot(self):
        """Test snapshot generation."""
        service = SectorRadarService()

        stocks = [
            StockData(
                ts_code="000001.SZ",
                name="Test Stock",
                sector_id="sector_test",
                sector_name="Test Sector",
                close=Decimal("110"),
                ma20=Decimal("105"),
                ma60=Decimal("100"),
                is_limit_up=True,
                consecutive_gains=2,
            ),
        ]

        snapshot = asyncio.run(
            service.generate_snapshot(
                sector_id="sector_test",
                snapshot_date=date.today(),
                stocks=stocks,
            )
        )

        assert snapshot.sector_id == "sector_test"
        assert snapshot.sector_name == "Test Sector"
        assert snapshot.snapshot_date == date.today()
        assert snapshot.technical_score is not None
        assert snapshot.sentiment_score is not None
        assert snapshot.composite_score is not None
        assert snapshot.state is not None

    def test_determine_state_weak(self):
        """Test state determination for weak sector."""
        service = SectorRadarService()
        state = service._determine_state(Decimal("0.2"))
        assert state == SectorState.weak

    def test_determine_state_normal(self):
        """Test state determination for normal sector."""
        service = SectorRadarService()
        state = service._determine_state(Decimal("0.5"))
        assert state == SectorState.normal

    def test_determine_state_overheated(self):
        """Test state determination for overheated sector."""
        service = SectorRadarService()
        state = service._determine_state(Decimal("0.85"))
        assert state == SectorState.overheated

    def test_determine_state_boundary_weak_normal(self):
        """Test state determination at weak/normal boundary."""
        service = SectorRadarService()

        # Just below threshold
        state = service._determine_state(Decimal("0.34"))
        assert state == SectorState.weak

        # At threshold
        state = service._determine_state(Decimal("0.35"))
        assert state == SectorState.normal

    def test_determine_state_boundary_normal_overheated(self):
        """Test state determination at normal/overheated boundary."""
        service = SectorRadarService()

        # Just below threshold
        state = service._determine_state(Decimal("0.69"))
        assert state == SectorState.normal

        # Above threshold
        state = service._determine_state(Decimal("0.71"))
        assert state == SectorState.overheated

    def test_generate_snapshot_empty_stocks(self):
        """Test snapshot generation with no stocks."""
        service = SectorRadarService()

        snapshot = asyncio.run(
            service.generate_snapshot(
                sector_id="sector_empty",
                snapshot_date=date.today(),
                stocks=[],
            )
        )

        assert snapshot.sector_id == "sector_empty"
        assert snapshot.technical_score == Decimal("0")
        assert snapshot.sentiment_score == Decimal("0")
        assert snapshot.composite_score == Decimal("0")
        assert snapshot.state == SectorState.weak


class TestSectorStateHysteresis:
    """Test sector state hysteresis logic."""

    def test_initial_state_weak(self):
        """Test initial state determination for low score."""
        state = SectorState.from_composite_score(Decimal("0.2"))
        assert state == SectorState.weak

    def test_initial_state_normal(self):
        """Test initial state determination for mid score."""
        state = SectorState.from_composite_score(Decimal("0.5"))
        assert state == SectorState.normal

    def test_initial_state_overheated(self):
        """Test initial state determination for high score."""
        state = SectorState.from_composite_score(Decimal("0.8"))
        assert state == SectorState.overheated

    def test_hysteresis_weak_to_normal(self):
        """Test hysteresis: weak -> normal requires score > 0.40."""
        # Score 0.38, previously weak -> stays weak
        state = SectorState.from_composite_score(Decimal("0.38"), SectorState.weak)
        assert state == SectorState.weak

        # Score 0.41, previously weak -> becomes normal
        state = SectorState.from_composite_score(Decimal("0.41"), SectorState.weak)
        assert state == SectorState.normal

    def test_hysteresis_normal_to_overheated(self):
        """Test hysteresis: normal -> overheated requires score > 0.75."""
        # Score 0.74, previously normal -> stays normal
        state = SectorState.from_composite_score(Decimal("0.74"), SectorState.normal)
        assert state == SectorState.normal

        # Score 0.76, previously normal -> becomes overheated
        state = SectorState.from_composite_score(Decimal("0.76"), SectorState.normal)
        assert state == SectorState.overheated

    def test_hysteresis_overheated_to_normal(self):
        """Test hysteresis: overheated -> normal requires score < 0.65."""
        # Score 0.66, previously overheated -> stays overheated
        state = SectorState.from_composite_score(Decimal("0.66"), SectorState.overheated)
        assert state == SectorState.overheated

        # Score 0.64, previously overheated -> becomes normal
        state = SectorState.from_composite_score(Decimal("0.64"), SectorState.overheated)
        assert state == SectorState.normal

    def test_hysteresis_normal_to_weak(self):
        """Test hysteresis: normal -> weak requires score < 0.30."""
        # Score 0.31, previously normal -> stays normal
        state = SectorState.from_composite_score(Decimal("0.31"), SectorState.normal)
        assert state == SectorState.normal

        # Score 0.29, previously normal -> becomes weak
        state = SectorState.from_composite_score(Decimal("0.29"), SectorState.normal)
        assert state == SectorState.weak


# Import asyncio for async tests
import asyncio


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
