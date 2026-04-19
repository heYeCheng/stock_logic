"""Unit tests for catalyst service."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.market.catalyst import CatalystService
from src.market.models import StockCatalyst


class MockEvent:
    """Mock event for testing."""

    def __init__(self, importance_level: str, logic_name: str = None):
        self.importance_level = importance_level
        self.logic_name = logic_name


class TestCatalystDetermination:
    """Test catalyst level determination."""

    def setup_method(self):
        self.service = CatalystService()

    def test_no_events_returns_none(self):
        """No events returns 'none' catalyst."""
        result = self.service.determine_catalyst([])
        assert result == "none"

    def test_one_high_importance_returns_medium(self):
        """One high-importance event returns 'medium' catalyst."""
        events = [MockEvent(importance_level="high")]
        result = self.service.determine_catalyst(events)
        assert result == "medium"

    def test_two_high_importance_returns_strong(self):
        """Two high-importance events returns 'strong' catalyst."""
        events = [
            MockEvent(importance_level="high"),
            MockEvent(importance_level="high"),
        ]
        result = self.service.determine_catalyst(events)
        assert result == "strong"

    def test_three_high_importance_returns_strong(self):
        """Three high-importance events returns 'strong' catalyst."""
        events = [
            MockEvent(importance_level="high"),
            MockEvent(importance_level="high"),
            MockEvent(importance_level="high"),
        ]
        result = self.service.determine_catalyst(events)
        assert result == "strong"

    def test_only_low_importance_returns_none(self):
        """Only low/medium importance events returns 'none' catalyst."""
        events = [
            MockEvent(importance_level="low"),
            MockEvent(importance_level="medium"),
        ]
        result = self.service.determine_catalyst(events)
        assert result == "none"

    def test_mixed_importance_counts_correctly(self):
        """Mixed importance events counted correctly."""
        events = [
            MockEvent(importance_level="high"),
            MockEvent(importance_level="low"),
            MockEvent(importance_level="medium"),
        ]
        result = self.service.determine_catalyst(events)
        assert result == "medium"


class TestDescriptionGeneration:
    """Test catalyst description generation."""

    def setup_method(self):
        self.service = CatalystService()

    def test_none_catalyst_description(self):
        """Description for 'none' catalyst."""
        description = self.service._build_description([], "none")
        assert description == "无显著催化剂"

    def test_strong_catalyst_with_logic_names(self):
        """Description for 'strong' catalyst with logic names."""
        events = [
            MockEvent(importance_level="high", logic_name="AI 大模型"),
            MockEvent(importance_level="high", logic_name="算力基建"),
            MockEvent(importance_level="high", logic_name="AI 大模型"),  # Duplicate
        ]
        description = self.service._build_description(events, "strong")
        assert "多重高重要性事件驱动" in description
        assert "AI 大模型" in description
        assert "算力基建" in description

    def test_medium_catalyst_with_logic_names(self):
        """Description for 'medium' catalyst with logic names."""
        events = [
            MockEvent(importance_level="high", logic_name="政策利好"),
        ]
        description = self.service._build_description(events, "medium")
        assert "重要事件驱动" in description
        assert "政策利好" in description

    def test_strong_catalyst_no_logic_names(self):
        """Description for 'strong' catalyst without logic names."""
        events = [
            MockEvent(importance_level="high", logic_name=None),
            MockEvent(importance_level="high", logic_name=None),
        ]
        description = self.service._build_description(events, "strong")
        assert description == "多重高重要性事件驱动"

    def test_medium_catalyst_no_logic_names(self):
        """Description for 'medium' catalyst without logic names."""
        events = [
            MockEvent(importance_level="high", logic_name=None),
        ]
        description = self.service._build_description(events, "medium")
        assert description == "重要事件驱动"


class TestLookbackWindow:
    """Test event lookback window."""

    def setup_method(self):
        self.service = CatalystService()

    def test_lookback_days_constant(self):
        """LOOKBACK_DAYS is set to 5."""
        assert self.service.LOOKBACK_DAYS == 5

    def test_date_calculation(self):
        """Test date range calculation."""
        snapshot_date = date(2026, 4, 19)
        expected_start = snapshot_date - timedelta(days=self.service.LOOKBACK_DAYS)
        assert expected_start == date(2026, 4, 14)
