"""Unit tests for lead concentration calculation using HHI."""

import pytest
from decimal import Decimal
from dataclasses import dataclass

from src.market.concentration import ConcentrationCalculator, ConcentrationQueries


@dataclass
class MockStock:
    """Mock stock object for testing."""
    code: str
    market_score: Decimal


class TestConcentrationCalculator:
    """Test HHI concentration calculation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = ConcentrationCalculator()

    def test_empty_sector(self):
        """Test concentration with no stocks."""
        stocks = []
        result = self.calculator.calculate(stocks)
        assert result == Decimal("0")

    def test_no_leader_candidates(self):
        """Test concentration when no stocks meet leader threshold."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.3")),
            MockStock(code="000002", market_score=Decimal("0.4")),
            MockStock(code="000003", market_score=Decimal("0.5")),  # Exactly 0.5, not > 0.5
        ]
        result = self.calculator.calculate(stocks)
        assert result == Decimal("0")

    def test_single_stock_max_concentration(self):
        """Test concentration with single stock = 1.0 (max concentration)."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.8")),
        ]
        result = self.calculator.calculate(stocks)
        assert result == Decimal("1")

    def test_equal_stocks_min_concentration(self):
        """Test concentration with equal stocks = 0.0 (min concentration)."""
        # Two stocks with equal scores should have HHI = 0.5, normalized = 0
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.6")),
            MockStock(code="000002", market_score=Decimal("0.6")),
        ]
        result = self.calculator.calculate(stocks)
        # HHI = (0.5)^2 + (0.5)^2 = 0.5
        # min_hhi for n=2 is 1/2 = 0.5
        # normalized = (0.5 - 0.5) / (1 - 0.5) = 0
        assert result == Decimal("0")

    def test_three_equal_stocks(self):
        """Test concentration with three equal stocks."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.6")),
            MockStock(code="000002", market_score=Decimal("0.6")),
            MockStock(code="000003", market_score=Decimal("0.6")),
        ]
        result = self.calculator.calculate(stocks)
        # Each share = 1/3, HHI = 3 * (1/3)^2 = 1/3
        # min_hhi for n=3 is 1/3
        # normalized = (1/3 - 1/3) / (1 - 1/3) = 0
        # Allow for small numerical precision errors
        assert abs(result) < Decimal("0.0001")

    def test_concentrated_leadership(self):
        """Test concentration with one dominant stock."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.9")),  # Dominant
            MockStock(code="000002", market_score=Decimal("0.55")),  # Just above threshold
            MockStock(code="000003", market_score=Decimal("0.55")),  # Just above threshold
        ]
        result = self.calculator.calculate(stocks)
        # Total = 2.0
        # Shares: 0.45, 0.275, 0.275
        # HHI = 0.45^2 + 0.275^2 + 0.275^2 = 0.2025 + 0.0756 + 0.0756 = 0.3537
        # min_hhi for n=3 is 1/3 = 0.333
        # normalized = (0.3537 - 0.333) / (1 - 0.333) = 0.0207 / 0.667 = 0.031
        # This is low concentration because the dominant stock isn't dominant enough
        assert result < Decimal("0.3")  # Should be low concentration

    def test_highly_concentrated(self):
        """Test concentration with very dominant stock."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("2.0")),  # Very dominant
            MockStock(code="000002", market_score=Decimal("0.55")),  # Just above threshold
            MockStock(code="000003", market_score=Decimal("0.55")),  # Just above threshold
        ]
        result = self.calculator.calculate(stocks)
        # Total = 3.1
        # Shares: 0.645, 0.177, 0.177
        # HHI = 0.645^2 + 0.177^2 + 0.177^2 = 0.416 + 0.031 + 0.031 = 0.478
        # min_hhi for n=3 is 1/3 = 0.333
        # normalized = (0.478 - 0.333) / (1 - 0.333) = 0.145 / 0.667 = 0.217
        # Still not high concentration
        assert result < Decimal("0.6")

    def test_extreme_concentration(self):
        """Test concentration with extremely dominant stock."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("10.0")),  # Extremely dominant
            MockStock(code="000002", market_score=Decimal("0.51")),  # Barely above threshold
        ]
        result = self.calculator.calculate(stocks)
        # Total = 10.51
        # Shares: 0.951, 0.049
        # HHI = 0.951^2 + 0.049^2 = 0.904 + 0.0024 = 0.9064
        # min_hhi for n=2 is 0.5
        # normalized = (0.9064 - 0.5) / (1 - 0.5) = 0.4064 / 0.5 = 0.813
        # This should be high concentration
        assert result > Decimal("0.6")

    def test_interpretation_high(self):
        """Test interpretation for high concentration."""
        assert self.calculator.interpret(Decimal("0.61")) == "high"
        assert self.calculator.interpret(Decimal("0.8")) == "high"
        assert self.calculator.interpret(Decimal("1.0")) == "high"

    def test_interpretation_medium(self):
        """Test interpretation for medium concentration."""
        assert self.calculator.interpret(Decimal("0.31")) == "medium"
        assert self.calculator.interpret(Decimal("0.5")) == "medium"
        assert self.calculator.interpret(Decimal("0.6")) == "medium"

    def test_interpretation_low(self):
        """Test interpretation for low concentration."""
        assert self.calculator.interpret(Decimal("0")) == "low"
        assert self.calculator.interpret(Decimal("0.1")) == "low"
        assert self.calculator.interpret(Decimal("0.3")) == "low"

    def test_boundary_exactly_0_6(self):
        """Test boundary at exactly 0.6."""
        # > 0.6 is high, so exactly 0.6 should be medium
        assert self.calculator.interpret(Decimal("0.6")) == "medium"
        assert self.calculator.interpret(Decimal("0.600001")) == "high"

    def test_boundary_exactly_0_3(self):
        """Test boundary at exactly 0.3."""
        # > 0.3 is medium, so exactly 0.3 should be low
        assert self.calculator.interpret(Decimal("0.3")) == "low"
        assert self.calculator.interpret(Decimal("0.300001")) == "medium"

    def test_leader_candidate_threshold(self):
        """Test leader candidate threshold (> 0.5, not >= 0.5)."""
        stock_at_threshold = MockStock(code="000001", market_score=Decimal("0.5"))
        stock_above_threshold = MockStock(code="000002", market_score=Decimal("0.500001"))
        stock_below_threshold = MockStock(code="000003", market_score=Decimal("0.499999"))

        assert self.calculator._is_leader_candidate(stock_at_threshold) is False
        assert self.calculator._is_leader_candidate(stock_above_threshold) is True
        assert self.calculator._is_leader_candidate(stock_below_threshold) is False

    def test_all_stocks_filtered_out(self):
        """Test when all stocks are filtered out as non-candidates."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.1")),
            MockStock(code="000002", market_score=Decimal("0.2")),
            MockStock(code="000003", market_score=Decimal("0.3")),
        ]
        result = self.calculator.calculate(stocks)
        assert result == Decimal("0")

    def test_total_strength_zero(self):
        """Test when total strength is zero (edge case)."""
        stocks = [
            MockStock(code="000001", market_score=Decimal("0")),
            MockStock(code="000002", market_score=Decimal("0")),
        ]
        # These would be filtered out by _is_leader_candidate since 0 is not > 0.5
        result = self.calculator.calculate(stocks)
        assert result == Decimal("0")

    def test_numerical_stability_clamping(self):
        """Test that result is clamped to [0, 1] range."""
        # Create a scenario that might produce edge results
        stocks = [
            MockStock(code="000001", market_score=Decimal("0.51")),
            MockStock(code="000002", market_score=Decimal("0.51")),
        ]
        result = self.calculator.calculate(stocks)
        assert Decimal("0") <= result <= Decimal("1")


class TestConcentrationQueries:
    """Test concentration query interface."""

    def test_init_default_session(self):
        """Test initialization with default session."""
        # Test initialization without session - session will be None
        queries = ConcentrationQueries()
        assert queries.session is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
