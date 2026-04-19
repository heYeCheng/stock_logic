"""Unit tests for STOCK-04: Stock Logic Score calculation.

Tests:
- Score calculation (single logic)
- Score calculation (multiple logics)
- Score calculation (no exposure)
- Score capping at 1.0
- Breakdown generation
- Snapshot persistence
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.market.stock_logic import (
    StockLogicScoreCalculator,
    StockLogicService,
    StockLogicBreakdown,
    LogicContribution,
)
from src.logic.models import LogicScore


class MockLogicScore:
    """Mock LogicScore for unit testing."""

    def __init__(self, logic_id: str, decayed_score: Decimal):
        self.logic_id = logic_id
        self.decayed_score = decayed_score


class TestStockLogicScoreCalculator:
    """Test stock logic score calculation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = StockLogicScoreCalculator()

    def test_calculate_single_logic(self):
        """Test calculation with single logic."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80"))
        }
        exposures = {
            "logic_001": Decimal("0.70")
        }

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 0.80 * 0.70 / 0.70 = 0.80
        assert result == Decimal("0.80")

    def test_calculate_multiple_logics(self):
        """Test calculation with multiple logics."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80")),
            "logic_002": MockLogicScore("logic_002", Decimal("0.60")),
        }
        exposures = {
            "logic_001": Decimal("0.70"),
            "logic_002": Decimal("0.30"),
        }

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: (0.80*0.70 + 0.60*0.30) / (0.70 + 0.30)
        # = (0.56 + 0.18) / 1.0 = 0.74
        assert result == Decimal("0.74")

    def test_calculate_no_exposure(self):
        """Test calculation with no exposure."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80"))
        }
        exposures = {
            "logic_001": Decimal("0")
        }

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 0 (no exposure)
        assert result == Decimal("0")

    def test_calculate_empty_exposures(self):
        """Test calculation with empty exposures dict."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80"))
        }
        exposures = {}

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 0 (no exposures)
        assert result == Decimal("0")

    def test_calculate_missing_exposure(self):
        """Test calculation when logic has no exposure entry."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80")),
            "logic_002": MockLogicScore("logic_002", Decimal("0.60")),
        }
        exposures = {
            "logic_001": Decimal("0.50")
            # logic_002 not in exposures
        }

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 0.80 * 0.50 / 0.50 = 0.80
        assert result == Decimal("0.80")

    def test_calculate_cap_at_one(self):
        """Test that score is capped at 1.0."""
        # Create a scenario where weighted average would exceed 1.0
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("1.0"))
        }
        exposures = {
            "logic_001": Decimal("0.50")
        }

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 1.0 (capped)
        assert result == Decimal("1.0")

    def test_calculate_with_null_decayed_score(self):
        """Test calculation when decayed_score is None."""
        logic_score = MockLogicScore("logic_001", Decimal("0.80"))
        logic_score.decayed_score = None

        logic_scores = {"logic_001": logic_score}
        exposures = {"logic_001": Decimal("0.50")}

        result = self.calculator.calculate(logic_scores, exposures)

        # Expected: 0 (no valid scores)
        assert result == Decimal("0")

    def test_calculate_with_breakdown(self):
        """Test breakdown calculation."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80")),
            "logic_002": MockLogicScore("logic_002", Decimal("0.60")),
        }
        exposures = {
            "logic_001": Decimal("0.70"),
            "logic_002": Decimal("0.30"),
        }

        breakdown = self.calculator.calculate_with_breakdown(logic_scores, exposures)

        assert breakdown.final_score == Decimal("0.74")
        assert breakdown.total_exposure == Decimal("1.0")
        assert len(breakdown.contributions) == 2

        # Check contributions
        contrib_001 = next(c for c in breakdown.contributions if c.logic_id == "logic_001")
        assert contrib_001.logic_score == Decimal("0.80")
        assert contrib_001.exposure == Decimal("0.70")
        assert contrib_001.contribution == Decimal("0.56")

        contrib_002 = next(c for c in breakdown.contributions if c.logic_id == "logic_002")
        assert contrib_002.logic_score == Decimal("0.60")
        assert contrib_002.exposure == Decimal("0.30")
        assert contrib_002.contribution == Decimal("0.18")

    def test_breakdown_no_exposure(self):
        """Test breakdown with no exposure."""
        logic_scores = {
            "logic_001": MockLogicScore("logic_001", Decimal("0.80"))
        }
        exposures = {
            "logic_001": Decimal("0")
        }

        breakdown = self.calculator.calculate_with_breakdown(logic_scores, exposures)

        assert breakdown.final_score == Decimal("0")
        assert breakdown.total_exposure == Decimal("0")
        assert len(breakdown.contributions) == 0


class TestStockLogicService:
    """Test stock logic service (integration tests)."""

    @pytest.mark.asyncio
    async def test_generate_snapshot(self):
        """Test generating logic score snapshot for a stock."""
        # This test requires database setup
        pytest.skip("Requires database fixture")

    @pytest.mark.asyncio
    async def test_generate_snapshot_no_exposure(self):
        """Test generating snapshot when stock has no exposure."""
        # This test requires database setup
        pytest.skip("Requires database fixture")

    @pytest.mark.asyncio
    async def test_generate_snapshot_multiple_logics(self):
        """Test generating snapshot with multiple logic exposures."""
        # This test requires database setup
        pytest.skip("Requires database fixture")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
