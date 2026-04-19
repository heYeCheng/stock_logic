"""Unit tests for HoldDecisionMaker service.

EXEC-04: Stop-Loss and Hold Decision Rules
Tests for decision logic, priority, and P&L calculation.
"""

import pytest
from decimal import Decimal

from src.market.hold_decision import HoldDecisionMaker


class TestHoldDecisionMaker:
    """Test cases for HoldDecisionMaker decision logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.maker = HoldDecisionMaker()

    # ==================== Stop-Loss Tests ====================

    def test_logic_stop_loss_trigger(self):
        """Test logic score below 0.3 triggers sell."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.25"),  # Below 0.3 threshold
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "sell"
        assert position == Decimal("0")
        assert "逻辑分" in reason

    def test_logic_stop_boundary(self):
        """Test logic score exactly at 0.3 does NOT trigger sell."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.3"),  # Exactly at threshold
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action != "sell"  # Should not trigger logic stop

    def test_price_stop_loss_8_percent(self):
        """Test price below entry x 0.92 triggers 8% stop-loss."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("100.00"),
            current_price=Decimal("91.00"),  # 9% loss
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "sell"
        assert position == Decimal("0")
        assert "价格止损" in reason

    def test_price_stop_boundary(self):
        """Test price exactly at 8% loss does NOT trigger stop-loss (strict < comparison)."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("100.00"),
            current_price=Decimal("92.00"),  # Exactly at 8% loss boundary
            sector_state="normal",
            catalyst_active=True,
        )

        # Note: Stop-loss triggers on STRICT less than (92.00 is not < 92.00)
        assert action == "hold"  # Boundary case - no trigger

    def test_price_no_stop_above_threshold(self):
        """Test price above 8% loss does NOT trigger stop-loss."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("100.00"),
            current_price=Decimal("93.00"),  # 7% loss
            sector_state="normal",
            catalyst_active=True,
        )

        assert action != "sell"  # Should not trigger price stop

    def test_catalyst_expired_sell(self):
        """Test catalyst expired + logic < 0.5 triggers sell."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.4"),  # Below 0.5
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=False,  # Catalyst expired
        )

        assert action == "sell"
        assert position == Decimal("0")
        assert "催化剂失效" in reason

    def test_catalyst_active_no_sell(self):
        """Test catalyst active does NOT trigger sell even with low logic."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.4"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action != "sell"  # Catalyst still active

    def test_catalyst_expired_logic_high_no_sell(self):
        """Test catalyst expired but logic >= 0.5 does NOT trigger sell."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.6"),  # Above 0.5
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=False,
        )

        assert action != "sell"

    # ==================== Reduction Tests ====================

    def test_sector_weak_reduce_50_percent(self):
        """Test sector weakness triggers 50% reduction."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="weak",
            catalyst_active=True,
        )

        assert action == "reduce"
        assert position == Decimal("500")  # 50% reduction
        assert "板块弱势" in reason

    def test_sector_normal_no_reduce(self):
        """Test sector normal does NOT trigger reduction."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action != "reduce"

    # ==================== Hold Tests ====================

    def test_hold_strong_logic(self):
        """Test logic score >= 0.7 triggers hold."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.7"),  # At threshold
            market_score=Decimal("0.4"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"
        assert position == Decimal("1000")
        assert "强逻辑分" in reason

    def test_hold_strong_market(self):
        """Test market score >= 0.7 triggers hold."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.7"),  # At threshold
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"
        assert "强市场分" in reason

    def test_hold_composite(self):
        """Test composite score >= 0.6 triggers hold."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.6"),  # At threshold
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"
        assert "综合分" in reason

    def test_hold_default_no_signal(self):
        """Test default hold when no strong signals."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"
        assert position == Decimal("1000")

    # ==================== Priority Tests ====================

    def test_priority_stop_loss_over_reduce(self):
        """Test stop-loss takes priority over reduction."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.2"),  # Logic stop triggered
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="weak",  # Would trigger reduce
            catalyst_active=True,
        )

        assert action == "sell"  # Stop-loss wins
        assert position == Decimal("0")

    def test_priority_stop_loss_over_hold(self):
        """Test stop-loss takes priority over hold."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.2"),  # Logic stop triggered
            market_score=Decimal("0.8"),  # Would trigger hold
            composite_score=Decimal("0.7"),  # Would trigger hold
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "sell"  # Stop-loss wins
        assert position == Decimal("0")

    def test_priority_reduce_over_hold(self):
        """Test reduction takes priority over hold."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.7"),  # Would trigger hold
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("10.00"),
            current_price=Decimal("10.50"),
            sector_state="weak",  # Reduce triggered
            catalyst_active=True,
        )

        assert action == "reduce"  # Reduction wins
        assert position == Decimal("500")

    # ==================== P&L Calculation Tests ====================

    def test_pnl_calculation_profit(self):
        """Test P&L calculation for profit scenario."""
        # Note: P&L is calculated internally but not returned
        # This test verifies the decision logic handles profit cases correctly
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("100.00"),
            current_price=Decimal("120.00"),  # 20% profit
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"

    def test_pnl_calculation_loss_not_triggered(self):
        """Test P&L calculation for loss not triggering stop."""
        action, position, reason = self.maker.make_decision(
            current_position=Decimal("1000"),
            logic_score=Decimal("0.5"),
            market_score=Decimal("0.5"),
            composite_score=Decimal("0.5"),
            entry_price=Decimal("100.00"),
            current_price=Decimal("95.00"),  # 5% loss
            sector_state="normal",
            catalyst_active=True,
        )

        assert action == "hold"  # Not enough to trigger stop

    # ==================== Method-Level Tests ====================

    def test_check_logic_stop_method(self):
        """Test check_logic_stop method directly."""
        triggered, reason = self.maker.check_logic_stop(Decimal("0.25"))
        assert triggered is True
        assert "逻辑分" in reason

        triggered, reason = self.maker.check_logic_stop(Decimal("0.35"))
        assert triggered is False
        assert reason == ""

    def test_check_price_stop_method(self):
        """Test check_price_stop method directly."""
        triggered, reason = self.maker.check_price_stop(
            Decimal("100.00"), Decimal("90.00")
        )
        assert triggered is True
        assert "价格止损" in reason

        triggered, reason = self.maker.check_price_stop(
            Decimal("100.00"), Decimal("95.00")
        )
        assert triggered is False
        assert reason == ""

    def test_check_sector_weak_method(self):
        """Test check_sector_weak method directly."""
        triggered, reason = self.maker.check_sector_weak("weak")
        assert triggered is True
        assert "板块弱势" in reason

        triggered, reason = self.maker.check_sector_weak("normal")
        assert triggered is False

    def test_check_hold_signals_method(self):
        """Test check_hold_signals method directly."""
        # Test strong logic
        triggered, reason = self.maker.check_hold_signals(
            Decimal("0.7"), Decimal("0.5"), Decimal("0.5")
        )
        assert triggered is True
        assert "强逻辑分" in reason

        # Test strong market
        triggered, reason = self.maker.check_hold_signals(
            Decimal("0.5"), Decimal("0.7"), Decimal("0.5")
        )
        assert triggered is True
        assert "强市场分" in reason

        # Test strong composite
        triggered, reason = self.maker.check_hold_signals(
            Decimal("0.5"), Decimal("0.5"), Decimal("0.6")
        )
        assert triggered is True
        assert "综合分" in reason

        # Test no hold signals
        triggered, reason = self.maker.check_hold_signals(
            Decimal("0.5"), Decimal("0.5"), Decimal("0.5")
        )
        assert triggered is False
