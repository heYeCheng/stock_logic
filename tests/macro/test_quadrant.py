"""Tests for macro quadrant analyzer."""

import pytest
from src.macro.quadrant import (
    QuadrantAnalyzer, Quadrant, MonetaryCondition, CreditCondition
)


class TestQuadrantAnalyzer:
    """Test quadrant determination logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = QuadrantAnalyzer()

    def test_wide_wide_quadrant(self):
        """Test wide-wide quadrant."""
        result = self.analyzer.analyze(
            m2_yoy=12.0,
            social_financing_yoy=18.0,
            composite_score=0.8
        )
        assert result.quadrant == Quadrant.WIDE_WIDE
        assert result.macro_multiplier > 1.0

    def test_tight_tight_quadrant(self):
        """Test tight-tight quadrant."""
        result = self.analyzer.analyze(
            m2_yoy=6.0,
            social_financing_yoy=8.0,
            composite_score=-0.8
        )
        assert result.quadrant == Quadrant.TIGHT_TIGHT
        assert result.macro_multiplier < 1.0

    def test_wide_tight_quadrant(self):
        """Test wide-tight quadrant (defensive)."""
        result = self.analyzer.analyze(
            m2_yoy=12.0,
            social_financing_yoy=8.0,
            composite_score=0.0
        )
        assert result.quadrant == Quadrant.WIDE_TIGHT
        assert result.macro_multiplier == 1.0

    def test_tight_wide_quadrant(self):
        """Test tight-wide quadrant (selective)."""
        result = self.analyzer.analyze(
            m2_yoy=6.0,
            social_financing_yoy=18.0,
            composite_score=0.0
        )
        assert result.quadrant == Quadrant.TIGHT_WIDE

    def test_neutral_conditions(self):
        """Test neutral monetary and credit conditions."""
        result = self.analyzer.analyze(
            m2_yoy=9.0,
            social_financing_yoy=12.0,
            composite_score=0.0
        )
        # Neutral-neutral maps to wide-tight (default defensive)
        assert result.monetary_condition == MonetaryCondition.NEUTRAL
        assert result.credit_condition == CreditCondition.NEUTRAL

    def test_multiplier_bounds(self):
        """Test multiplier is bounded [0.85, 1.15]."""
        # Max risk-on
        result = self.analyzer.analyze(
            m2_yoy=12.0,
            social_financing_yoy=18.0,
            composite_score=1.0
        )
        assert 0.85 <= result.macro_multiplier <= 1.15

        # Max risk-off
        result = self.analyzer.analyze(
            m2_yoy=6.0,
            social_financing_yoy=8.0,
            composite_score=-1.0
        )
        assert 0.85 <= result.macro_multiplier <= 1.15

    def test_multiplier_none_data(self):
        """Test multiplier with None data defaults to neutral."""
        result = self.analyzer.analyze(
            m2_yoy=None,
            social_financing_yoy=None,
            composite_score=0.0
        )
        assert result.macro_multiplier == 1.0
