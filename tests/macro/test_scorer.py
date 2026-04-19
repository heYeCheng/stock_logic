"""Tests for macro scorer."""

import pytest
from src.macro.scorer import MacroScorer


class TestMacroScorer:
    """Test macro scoring logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = MacroScorer()

    def test_liquidity_score_wide(self):
        """Test liquidity score when M2 is wide."""
        score = self.scorer.score_liquidity(m2_yoy=12.0)
        assert score == 1.0

    def test_liquidity_score_tight(self):
        """Test liquidity score when M2 is tight."""
        score = self.scorer.score_liquidity(m2_yoy=7.0)
        assert score == -1.0

    def test_liquidity_score_neutral(self):
        """Test liquidity score when M2 is neutral."""
        score = self.scorer.score_liquidity(m2_yoy=9.0)
        assert -0.5 < score < 0.5

    def test_liquidity_score_none(self):
        """Test liquidity score when M2 is None."""
        score = self.scorer.score_liquidity(m2_yoy=None)
        assert score == 0.0

    def test_growth_score_strong(self):
        """Test growth score when PMI is strong."""
        score = self.scorer.score_growth(pmi=53.0)
        assert score > 0.5

    def test_growth_score_weak(self):
        """Test growth score when PMI is weak."""
        score = self.scorer.score_growth(pmi=47.0)
        assert score < -0.5

    def test_growth_score_neutral(self):
        """Test growth score when PMI is neutral."""
        score = self.scorer.score_growth(pmi=50.0)
        assert score == 0.0

    def test_inflation_score_optimal(self):
        """Test inflation score when CPI is in optimal range."""
        score = self.scorer.score_inflation(cpi_yoy=2.5)
        assert score > 0

    def test_inflation_score_high(self):
        """Test inflation score when CPI is high."""
        score = self.scorer.score_inflation(cpi_yoy=6.0)
        assert score < 0

    def test_inflation_score_deflation(self):
        """Test inflation score when CPI is negative (deflation)."""
        score = self.scorer.score_inflation(cpi_yoy=-1.0)
        assert score < 0

    def test_global_score_weak_dollar(self):
        """Test global score when dollar is weak."""
        score = self.scorer.score_global(dxy=93.0)
        assert score > 0

    def test_global_score_strong_dollar(self):
        """Test global score when dollar is strong."""
        score = self.scorer.score_global(dxy=112.0)
        assert score < 0

    def test_score_all(self):
        """Test scoring all dimensions."""
        indicators = {
            'm2_yoy': 9.5,
            'pmi_manufacturing': 51.0,
            'cpi_yoy': 2.0,
            'fed_rate': 4.0,
            'dxy_index': 102.0
        }
        scores = self.scorer.score_all(indicators)

        assert 'liquidity_score' in scores
        assert 'growth_score' in scores
        assert 'inflation_score' in scores
        assert 'policy_score' in scores
        assert 'global_score' in scores
        assert 'composite_score' in scores

        # All scores should be in [-1, 1] range
        for key, value in scores.items():
            assert -1.0 <= value <= 1.0, f"{key} score {value} out of range"
