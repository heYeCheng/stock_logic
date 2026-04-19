"""Unit tests for marker classification service."""

import pytest
from decimal import Decimal

from src.market.marker import MarkerClassifier, MarkerService


class TestMarkerClassifier:
    """Test marker classification logic."""

    def setup_method(self):
        self.classifier = MarkerClassifier()

    def test_logic_beneficiary_high_logic_high_exposure(self):
        """Logic beneficiary: logic >= 0.7 AND exposure >= 0.5."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.75"),
            market_score=Decimal("0.60"),
            exposure_coefficient=Decimal("0.55"),
            catalyst_level="strong",
        )
        assert marker == "逻辑受益股"
        assert "高逻辑分" in reason
        assert "强暴露" in reason

    def test_logic_beneficiary_exact_threshold(self):
        """Logic beneficiary at exact threshold (0.7, 0.5)."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.7"),
            market_score=Decimal("0.50"),
            exposure_coefficient=Decimal("0.5"),
            catalyst_level="medium",
        )
        assert marker == "逻辑受益股"
        assert "高逻辑分" in reason

    def test_related_beneficiary_medium_logic_medium_exposure(self):
        """Related beneficiary: logic >= 0.4 AND exposure >= 0.3."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.50"),
            market_score=Decimal("0.40"),
            exposure_coefficient=Decimal("0.35"),
            catalyst_level="none",
        )
        assert marker == "关联受益股"
        assert "中等逻辑分" in reason
        assert "中等暴露" in reason

    def test_related_beneficiary_exact_threshold(self):
        """Related beneficiary at exact threshold (0.4, 0.3)."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.4"),
            market_score=Decimal("0.30"),
            exposure_coefficient=Decimal("0.3"),
            catalyst_level="none",
        )
        assert marker == "关联受益股"

    def test_sentiment_follower_high_market_low_logic(self):
        """Sentiment follower: market >= 0.6 AND logic < 0.4."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.30"),
            market_score=Decimal("0.70"),
            exposure_coefficient=Decimal("0.20"),
            catalyst_level="none",
        )
        assert marker == "情绪跟风股"
        assert "高市场分" in reason
        assert "低逻辑分" in reason

    def test_sentiment_follower_exact_threshold(self):
        """Sentiment follower at exact threshold (market=0.6, logic<0.4)."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.39"),
            market_score=Decimal("0.6"),
            exposure_coefficient=Decimal("0.20"),
            catalyst_level="none",
        )
        assert marker == "情绪跟风股"

    def test_default_logic_beneficiary_fallback(self):
        """Default fallback to logic beneficiary when logic >= 0.4."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.45"),
            market_score=Decimal("0.30"),
            exposure_coefficient=Decimal("0.25"),
            catalyst_level="none",
        )
        assert marker == "逻辑受益股"
        assert "逻辑分" in reason

    def test_default_sentiment_follower_fallback(self):
        """Default fallback to sentiment follower when logic < 0.4."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.20"),
            market_score=Decimal("0.40"),
            exposure_coefficient=Decimal("0.10"),
            catalyst_level="none",
        )
        assert marker == "情绪跟风股"
        assert "市场分" in reason


class TestBoundaryConditions:
    """Test boundary conditions at thresholds."""

    def setup_method(self):
        self.classifier = MarkerClassifier()

    def test_just_below_logic_high_threshold(self):
        """Logic score just below 0.7 should not be logic beneficiary."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.69"),
            market_score=Decimal("0.50"),
            exposure_coefficient=Decimal("0.55"),
            catalyst_level="strong",
        )
        # Falls to related beneficiary (medium logic + high exposure)
        assert marker == "关联受益股"

    def test_just_below_exposure_high_threshold(self):
        """Exposure just below 0.5 should not be logic beneficiary."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.75"),
            market_score=Decimal("0.50"),
            exposure_coefficient=Decimal("0.49"),
            catalyst_level="strong",
        )
        # Falls to related beneficiary (high logic but only medium exposure)
        assert marker == "关联受益股"

    def test_just_below_logic_medium_threshold(self):
        """Logic score just below 0.4 with high market should be sentiment follower."""
        marker, reason = self.classifier.classify_marker(
            logic_score=Decimal("0.39"),
            market_score=Decimal("0.65"),
            exposure_coefficient=Decimal("0.25"),
            catalyst_level="none",
        )
        assert marker == "情绪跟风股"


class TestReasonGeneration:
    """Test reason string generation."""

    def setup_method(self):
        self.classifier = MarkerClassifier()

    def test_build_reason_high_scores(self):
        """Build reason with all high scores."""
        reason = self.classifier.build_reason(
            marker="逻辑受益股",
            logic_score=Decimal("0.80"),
            market_score=Decimal("0.70"),
            exposure_coefficient=Decimal("0.60"),
            catalyst_level="strong",
        )
        assert "高逻辑分" in reason
        assert "高市场分" in reason
        assert "强暴露" in reason
        assert "强催化剂" in reason

    def test_build_reason_medium_scores(self):
        """Build reason with medium scores."""
        reason = self.classifier.build_reason(
            marker="关联受益股",
            logic_score=Decimal("0.50"),
            market_score=Decimal("0.40"),
            exposure_coefficient=Decimal("0.35"),
            catalyst_level="medium",
        )
        assert "中等逻辑分" in reason
        assert "中等催化剂" in reason

    def test_build_reason_low_scores(self):
        """Build reason with low scores."""
        reason = self.classifier.build_reason(
            marker="情绪跟风股",
            logic_score=Decimal("0.20"),
            market_score=Decimal("0.30"),
            exposure_coefficient=Decimal("0.15"),
            catalyst_level="none",
        )
        assert "低逻辑分" in reason

    def test_reason_chinese_formatting(self):
        """Reason uses Chinese comma separator."""
        reason = self.classifier.build_reason(
            marker="逻辑受益股",
            logic_score=Decimal("0.80"),
            market_score=Decimal("0.70"),
            exposure_coefficient=Decimal("0.60"),
            catalyst_level="strong",
        )
        assert "，" in reason
