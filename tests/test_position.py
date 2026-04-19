"""Unit tests for EXEC-01: Continuous Position Function.

Tests:
- Sigmoid function (boundary values)
- Base position calculation (0, 0.5, 1.0 composite)
- Macro overlay (various multipliers)
- Sector overlay (weak/normal/overheated)
- Position tier boundaries
- Full calculation integration
"""

import pytest
from decimal import Decimal

from src.market.position import PositionCalculator
from src.market.models import SectorState


class TestSigmoidFunction:
    """Test sigmoid function for smooth scaling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_sigmoid_zero(self):
        """Test sigmoid(0) = 0.5."""
        result = self.calc.sigmoid(Decimal("0"))
        assert abs(float(result) - 0.5) < 0.0001

    def test_sigmoid_positive(self):
        """Test sigmoid with positive input."""
        result = self.calc.sigmoid(Decimal("1"))
        # sigmoid(1) = 1 / (1 + e^-1) ≈ 0.731
        assert 0.7 < result < 0.8

    def test_sigmoid_negative(self):
        """Test sigmoid with negative input."""
        result = self.calc.sigmoid(Decimal("-1"))
        # sigmoid(-1) = 1 / (1 + e^1) ≈ 0.269
        assert 0.2 < result < 0.3

    def test_sigmoid_large_positive(self):
        """Test sigmoid approaches 1 for large positive values."""
        result = self.calc.sigmoid(Decimal("5"))
        assert result > Decimal("0.99")

    def test_sigmoid_large_negative(self):
        """Test sigmoid approaches 0 for large negative values."""
        result = self.calc.sigmoid(Decimal("-5"))
        assert result < Decimal("0.01")


class TestBasePositionCalculation:
    """Test base position calculation from composite score."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_base_position_zero_composite(self):
        """Test base position with composite_score = 0."""
        # sigmoid(0 * 2 - 1) = sigmoid(-1) ≈ 0.269
        result = self.calc.calculate_base_position(Decimal("0"))
        assert 0.25 < result < 0.30

    def test_base_position_mid_composite(self):
        """Test base position with composite_score = 0.5."""
        # sigmoid(0.5 * 2 - 1) = sigmoid(0) = 0.5
        result = self.calc.calculate_base_position(Decimal("0.5"))
        assert abs(float(result) - 0.5) < 0.0001

    def test_base_position_full_composite(self):
        """Test base position with composite_score = 1.0."""
        # sigmoid(1.0 * 2 - 1) = sigmoid(1) ≈ 0.731
        result = self.calc.calculate_base_position(Decimal("1.0"))
        assert 0.7 < result < 0.75


class TestMacroOverlay:
    """Test macro multiplier overlay."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_macro_multiplier_one(self):
        """Test macro multiplier = 1.0 (no change)."""
        base = Decimal("0.5")
        result = self.calc.apply_macro_overlay(base, Decimal("1.0"))
        assert result == Decimal("0.5")

    def test_macro_multiplier_high(self):
        """Test macro multiplier = 1.5 (bullish)."""
        base = Decimal("0.5")
        result = self.calc.apply_macro_overlay(base, Decimal("1.5"))
        assert result == Decimal("0.75")

    def test_macro_multiplier_low(self):
        """Test macro multiplier = 0.5 (bearish)."""
        base = Decimal("0.5")
        result = self.calc.apply_macro_overlay(base, Decimal("0.5"))
        assert result == Decimal("0.25")


class TestSectorOverlay:
    """Test sector state overlay."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_sector_normal(self):
        """Test sector state = normal (no change)."""
        position = Decimal("0.6")
        result = self.calc.apply_sector_overlay(position, SectorState.normal)
        assert result == Decimal("0.6")

    def test_sector_weak(self):
        """Test sector state = weak (50% reduction)."""
        position = Decimal("0.6")
        result = self.calc.apply_sector_overlay(position, SectorState.weak)
        assert result == Decimal("0.3")

    def test_sector_overheated(self):
        """Test sector state = overheated (30% reduction)."""
        position = Decimal("0.6")
        result = self.calc.apply_sector_overlay(position, SectorState.overheated)
        assert result == Decimal("0.42")


class TestPositionTierMapping:
    """Test position tier mapping."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_tier_empty(self):
        """Test 空仓 (empty) tier for position < 0.10."""
        assert self.calc.get_position_tier(Decimal("0.05")) == "空仓"
        assert self.calc.get_position_tier(Decimal("0.09")) == "空仓"

    def test_tier_light(self):
        """Test 轻仓 (light) tier for 0.10 <= position < 0.30."""
        assert self.calc.get_position_tier(Decimal("0.10")) == "轻仓"
        assert self.calc.get_position_tier(Decimal("0.20")) == "轻仓"
        assert self.calc.get_position_tier(Decimal("0.29")) == "轻仓"

    def test_tier_moderate(self):
        """Test 中等 (moderate) tier for 0.30 <= position < 0.60."""
        assert self.calc.get_position_tier(Decimal("0.30")) == "中等"
        assert self.calc.get_position_tier(Decimal("0.45")) == "中等"
        assert self.calc.get_position_tier(Decimal("0.59")) == "中等"

    def test_tier_heavy(self):
        """Test 重仓 (heavy) tier for 0.60 <= position < 0.80."""
        assert self.calc.get_position_tier(Decimal("0.60")) == "重仓"
        assert self.calc.get_position_tier(Decimal("0.70")) == "重仓"
        assert self.calc.get_position_tier(Decimal("0.79")) == "重仓"

    def test_tier_full(self):
        """Test 满仓 (full) tier for position >= 0.80."""
        assert self.calc.get_position_tier(Decimal("0.80")) == "满仓"
        assert self.calc.get_position_tier(Decimal("0.90")) == "满仓"
        assert self.calc.get_position_tier(Decimal("1.0")) == "满仓"


class TestFullPositionCalculation:
    """Test full position calculation integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_full_calc_bullish(self):
        """Test full calculation with bullish conditions."""
        # High composite, high macro, normal sector
        result = self.calc.calculate_position(
            composite_score=Decimal("0.8"),
            macro_multiplier=Decimal("1.5"),
            sector_state=SectorState.normal
        )
        # base = sigmoid(0.8 * 2 - 1) = sigmoid(0.6) ≈ 0.646
        # macro = 0.646 * 1.5 ≈ 0.969
        # sector = 0.969 * 1.0 = 0.969
        assert 0.9 < result <= 1.0
        assert self.calc.get_position_tier(result) == "满仓"

    def test_full_calc_bearish(self):
        """Test full calculation with bearish conditions."""
        # Low composite, low macro, weak sector
        result = self.calc.calculate_position(
            composite_score=Decimal("0.2"),
            macro_multiplier=Decimal("0.5"),
            sector_state=SectorState.weak
        )
        # base = sigmoid(0.2 * 2 - 1) = sigmoid(-0.6) ≈ 0.354
        # macro = 0.354 * 0.5 ≈ 0.177
        # sector = 0.177 * 0.5 ≈ 0.089
        assert result < Decimal("0.1")
        assert self.calc.get_position_tier(result) == "空仓"

    def test_full_calc_neutral(self):
        """Test full calculation with neutral conditions."""
        # Mid composite, normal macro, normal sector
        result = self.calc.calculate_position(
            composite_score=Decimal("0.5"),
            macro_multiplier=Decimal("1.0"),
            sector_state=SectorState.normal
        )
        # base = sigmoid(0) = 0.5
        # macro = 0.5 * 1.0 = 0.5
        # sector = 0.5 * 1.0 = 0.5
        assert 0.49 < result < 0.51
        assert self.calc.get_position_tier(result) == "中等"

    def test_full_calc_clamping(self):
        """Test that result is clamped to 0-1 range."""
        # Extreme bullish should not exceed 1.0
        result_high = self.calc.calculate_position(
            composite_score=Decimal("1.0"),
            macro_multiplier=Decimal("1.5"),
            sector_state=SectorState.normal
        )
        assert result_high <= Decimal("1")
        assert result_high >= Decimal("0")

        # Extreme bearish should not go below 0
        result_low = self.calc.calculate_position(
            composite_score=Decimal("0"),
            macro_multiplier=Decimal("0.5"),
            sector_state=SectorState.weak
        )
        assert result_low >= Decimal("0")


class TestPositionTierDocumentations:
    """Test position tier documentation and boundaries.

    Position tiers (EXEC-01):
    - 空仓 (empty): 0-10% - No position or very small position
    - 轻仓 (light): 10-30% - Small position for testing
    - 中等 (moderate): 30-60% - Standard position
    - 重仓 (heavy): 60-80% - Large position for high conviction
    - 满仓 (full): 80-100% - Maximum position
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = PositionCalculator()

    def test_tier_boundaries_documented(self):
        """Verify tier boundary constants match documentation."""
        assert self.calc.TIER_EMPTY == Decimal("0.10")
        assert self.calc.TIER_LIGHT == Decimal("0.30")
        assert self.calc.TIER_MODERATE == Decimal("0.60")
        assert self.calc.TIER_HEAVY == Decimal("0.80")

    def test_sector_multipliers_documented(self):
        """Verify sector state multipliers match documentation."""
        assert self.calc.STATE_MULTIPLIERS[SectorState.weak] == Decimal("0.5")
        assert self.calc.STATE_MULTIPLIERS[SectorState.normal] == Decimal("1.0")
        assert self.calc.STATE_MULTIPLIERS[SectorState.overheated] == Decimal("0.7")
