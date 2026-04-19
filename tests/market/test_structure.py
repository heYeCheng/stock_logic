"""Tests for market structure markers.

Tests for MARKET-04: Structure Markers (聚焦/扩散/快速轮动/正常)
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from src.market.structure import StructureMarkerService, StructureMarker, StructureQueries
from src.market.sector_radar import StockData


class TestStructureMarkerService:
    """Test structure marker service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = StructureMarkerService()

    def test_marker_focus_high_concentration_low_breadth(self):
        """Test 聚焦 marker: high concentration + low breadth."""
        # concentration > 0.6 AND breadth < 0.4
        marker = self.service.determine_marker(
            concentration=Decimal("0.75"),
            breadth=Decimal("0.25"),
            turnover=Decimal("1.0")
        )
        assert marker == "聚焦"

    def test_marker_focus_boundary_exact(self):
        """Test 聚焦 marker at exact boundary."""
        # Exactly at threshold - should NOT be 聚焦 (needs to be > 0.6 and < 0.4)
        marker = self.service.determine_marker(
            concentration=Decimal("0.6"),  # Exactly at threshold
            breadth=Decimal("0.4"),
            turnover=Decimal("1.0")
        )
        assert marker == "正常"  # Not 聚焦 because not strictly greater/less

    def test_marker_diffuse_low_concentration_high_breadth(self):
        """Test 扩散 marker: low concentration + high breadth."""
        # concentration < 0.4 AND breadth > 0.6
        marker = self.service.determine_marker(
            concentration=Decimal("0.25"),
            breadth=Decimal("0.75"),
            turnover=Decimal("1.0")
        )
        assert marker == "扩散"

    def test_marker_rotation_high_turnover(self):
        """Test 快速轮动 marker: high turnover."""
        # turnover > 1.5
        marker = self.service.determine_marker(
            concentration=Decimal("0.5"),
            breadth=Decimal("0.5"),
            turnover=Decimal("1.8")
        )
        assert marker == "快速轮动"

    def test_marker_rotation_turnover_boundary(self):
        """Test 快速轮动 marker at exact boundary."""
        # Exactly at threshold - should NOT be 快速轮动 (needs to be > 1.5)
        marker = self.service.determine_marker(
            concentration=Decimal("0.5"),
            breadth=Decimal("0.5"),
            turnover=Decimal("1.5")  # Exactly at threshold
        )
        assert marker == "正常"

    def test_marker_normal_default(self):
        """Test 正常 marker: default when no conditions met."""
        # Medium concentration, medium breadth, low turnover
        marker = self.service.determine_marker(
            concentration=Decimal("0.5"),
            breadth=Decimal("0.5"),
            turnover=Decimal("1.0")
        )
        assert marker == "正常"

    def test_marker_normal_mixed_signals(self):
        """Test 正常 marker: mixed signals that don't match any pattern."""
        # High concentration but also high breadth (contradictory for 聚焦)
        marker = self.service.determine_marker(
            concentration=Decimal("0.7"),
            breadth=Decimal("0.7"),
            turnover=Decimal("1.0")
        )
        assert marker == "正常"

    def test_confidence_focus_strong(self):
        """Test confidence calculation for 聚焦 with strong signals."""
        confidence = self.service.calculate_confidence(
            concentration=Decimal("0.8"),  # 0.2 above threshold
            breadth=Decimal("0.2"),  # 0.2 below threshold
            turnover=Decimal("1.0"),
            marker="聚焦"
        )
        # Both distances are 0.2, min should be 0.2
        assert confidence == 0.2

    def test_confidence_focus_weak(self):
        """Test confidence calculation for 聚焦 near boundary."""
        confidence = self.service.calculate_confidence(
            concentration=Decimal("0.61"),  # Just barely above threshold
            breadth=Decimal("0.39"),  # Just barely below threshold
            turnover=Decimal("1.0"),
            marker="聚焦"
        )
        # Both distances are 0.01
        assert abs(confidence - 0.01) < 0.001

    def test_confidence_diffuse_strong(self):
        """Test confidence calculation for 扩散 with strong signals."""
        confidence = self.service.calculate_confidence(
            concentration=Decimal("0.2"),  # 0.2 below threshold
            breadth=Decimal("0.8"),  # 0.2 above threshold
            turnover=Decimal("1.0"),
            marker="扩散"
        )
        # Both distances are 0.2
        assert confidence == 0.2

    def test_confidence_rotation(self):
        """Test confidence calculation for 快速轮动."""
        confidence = self.service.calculate_confidence(
            concentration=Decimal("0.5"),
            breadth=Decimal("0.5"),
            turnover=Decimal("2.25"),  # 0.75 above threshold
            marker="快速轮动"
        )
        # Normalized: 0.75 / 1.5 = 0.5
        assert confidence == 0.5

    def test_confidence_normal(self):
        """Test confidence calculation for 正常."""
        confidence = self.service.calculate_confidence(
            concentration=Decimal("0.5"),
            breadth=Decimal("0.5"),
            turnover=Decimal("1.0"),
            marker="正常"
        )
        # Should have positive confidence (distance from boundaries)
        assert confidence > 0

    def test_breadth_calculation_all_above_ma(self):
        """Test breadth calculation when all stocks above MA20."""
        stocks = [
            StockData(ts_code=f"stock{i}", name=f"Stock {i}", sector_id="test", close=Decimal("10.5"), ma20=Decimal("10.0"))
            for i in range(10)
        ]
        breadth = self.service.calculate_breadth(stocks)
        assert breadth == Decimal("1.0")

    def test_breadth_calculation_half_above_ma(self):
        """Test breadth calculation when half stocks above MA20."""
        stocks = []
        for i in range(10):
            if i < 5:
                # Above MA20
                stocks.append(StockData(ts_code=f"stock{i}", name=f"Stock {i}", sector_id="test", close=Decimal("10.5"), ma20=Decimal("10.0")))
            else:
                # Below MA20
                stocks.append(StockData(ts_code=f"stock{i}", name=f"Stock {i}", sector_id="test", close=Decimal("9.5"), ma20=Decimal("10.0")))
        breadth = self.service.calculate_breadth(stocks)
        assert breadth == Decimal("0.5")

    def test_breadth_calculation_empty(self):
        """Test breadth calculation with no stocks."""
        breadth = self.service.calculate_breadth([])
        assert breadth == Decimal("0")

    @pytest.mark.asyncio
    async def test_generate_marker_full(self):
        """Test full marker generation."""
        stocks = []
        for i in range(10):
            if i < 3:
                # 3 out of 10 above MA20 = 0.3 breadth
                stocks.append(StockData(ts_code=f"stock{i}", name=f"Stock {i}", sector_id="test_sector", close=Decimal("10.5"), ma20=Decimal("10.0")))
            else:
                stocks.append(StockData(ts_code=f"stock{i}", name=f"Stock {i}", sector_id="test_sector", close=Decimal("9.5"), ma20=Decimal("10.0")))

        # Mock concentration and turnover
        marker = await self.service.generate_marker(
            sector_id="test_sector",
            snapshot_date=date.today(),
            stocks=stocks,
            concentration=Decimal("0.7"),  # High concentration
            turnover=Decimal("1.0")  # Normal turnover
        )

        assert marker.sector_id == "test_sector"
        assert marker.snapshot_date == date.today()
        assert marker.marker == "聚焦"  # High conc + low breadth
        assert marker.concentration == Decimal("0.7")
        assert marker.breadth == Decimal("0.3")
        assert marker.turnover == Decimal("1.0")
        assert marker.confidence > 0


class TestStructureQueries:
    """Test structure query interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.queries = StructureQueries()

    @pytest.mark.asyncio
    async def test_get_current_markers_empty(self):
        """Test getting current markers (placeholder - returns empty)."""
        markers = await self.queries.get_current_markers()
        assert isinstance(markers, dict)

    @pytest.mark.asyncio
    async def test_get_sectors_by_marker(self):
        """Test getting sectors by marker (placeholder)."""
        sectors = await self.queries.get_sectors_by_marker("聚焦")
        assert isinstance(sectors, list)

    @pytest.mark.asyncio
    async def test_get_marker_history(self):
        """Test getting marker history (placeholder)."""
        history = await self.queries.get_marker_history("test_sector", days=30)
        assert isinstance(history, list)


class TestStructureMarkerDataclass:
    """Test StructureMarker dataclass."""

    def test_create_marker(self):
        """Test creating a StructureMarker."""
        marker = StructureMarker(
            sector_id="test",
            snapshot_date=date(2026, 4, 19),
            marker="聚焦",
            concentration=Decimal("0.75"),
            breadth=Decimal("0.3"),
            turnover=Decimal("1.2"),
            confidence=0.15
        )

        assert marker.sector_id == "test"
        assert marker.snapshot_date == date(2026, 4, 19)
        assert marker.marker == "聚焦"
        assert marker.concentration == Decimal("0.75")
        assert marker.breadth == Decimal("0.3")
        assert marker.turnover == Decimal("1.2")
        assert marker.confidence == 0.15

    def test_marker_repr(self):
        """Test StructureMarker string representation."""
        marker = StructureMarker(
            sector_id="test",
            snapshot_date=date(2026, 4, 19),
            marker="扩散",
            concentration=Decimal("0.3"),
            breadth=Decimal("0.7"),
            turnover=Decimal("1.0"),
            confidence=0.1
        )
        # Just verify it doesn't crash
        repr(marker)
