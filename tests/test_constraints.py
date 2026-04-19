"""Unit tests for A-share trading constraint enforcement (EXEC-02)."""

import pytest
from decimal import Decimal

from src.market.constraints import ConstraintChecker, ConstraintService


class TestLimitThresholdDetection:
    """Test limit threshold detection by stock type."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_main_board_threshold(self):
        """Main board stocks have 10% limit."""
        assert self.checker.get_limit_threshold("000001.SZ") == Decimal("0.10")
        assert self.checker.get_limit_threshold("000002.SZ") == Decimal("0.10")
        assert self.checker.get_limit_threshold("600000.SH") == Decimal("0.10")

    def test_st_stock_threshold(self):
        """ST stocks have 5% limit."""
        assert self.checker.get_limit_threshold("ST0001.SZ") == Decimal("0.05")
        assert self.checker.get_limit_threshold("*ST0002.SZ") == Decimal("0.05")
        assert self.checker.get_limit_threshold("600ST0.SH") == Decimal("0.05")

    def test_star_market_threshold(self):
        """STAR Market (688xxx) stocks have 20% limit."""
        assert self.checker.get_limit_threshold("688001.SH") == Decimal("0.20")
        assert self.checker.get_limit_threshold("688999.SH") == Decimal("0.20")


class TestLimitStatusCheck:
    """Test limit status check (up/down/normal)."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_limit_up_main_board(self):
        """Main board stock at +10% is limit up."""
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("11.00"),
            prev_close=Decimal("10.00")
        )
        assert result == "limit_up"

    def test_limit_down_main_board(self):
        """Main board stock at -10% is limit down."""
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("9.00"),
            prev_close=Decimal("10.00")
        )
        assert result == "limit_down"

    def test_normal_main_board(self):
        """Main board stock at +5% is normal."""
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("10.50"),
            prev_close=Decimal("10.00")
        )
        assert result == "normal"

    def test_limit_up_st_stock(self):
        """ST stock at +5% is limit up."""
        result = self.checker.check_limit_status(
            stock_code="ST0001.SZ",
            current_price=Decimal("10.50"),
            prev_close=Decimal("10.00")
        )
        assert result == "limit_up"

    def test_limit_down_st_stock(self):
        """ST stock at -5% is limit down."""
        result = self.checker.check_limit_status(
            stock_code="ST0001.SZ",
            current_price=Decimal("9.50"),
            prev_close=Decimal("10.00")
        )
        assert result == "limit_down"

    def test_limit_up_star_market(self):
        """STAR Market stock at +20% is limit up."""
        result = self.checker.check_limit_status(
            stock_code="688001.SH",
            current_price=Decimal("120.00"),
            prev_close=Decimal("100.00")
        )
        assert result == "limit_up"

    def test_limit_down_star_market(self):
        """STAR Market stock at -20% is limit down."""
        result = self.checker.check_limit_status(
            stock_code="688001.SH",
            current_price=Decimal("80.00"),
            prev_close=Decimal("100.00")
        )
        assert result == "limit_down"

    def test_zero_prev_close_returns_normal(self):
        """Zero previous close returns normal."""
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("10.00"),
            prev_close=Decimal("0")
        )
        assert result == "normal"

    def test_tolerance_at_boundary(self):
        """Small tolerance at boundary."""
        # Just below limit (9.9%) should still be normal
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("10.98"),
            prev_close=Decimal("10.00")
        )
        assert result == "normal"

        # At limit (10%) should be limit up
        result = self.checker.check_limit_status(
            stock_code="000001.SZ",
            current_price=Decimal("11.00"),
            prev_close=Decimal("10.00")
        )
        assert result == "limit_up"


class TestSuspensionCheck:
    """Test suspension check."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_suspended_true(self):
        """Suspend flag True returns True."""
        assert self.checker.check_suspension(True) is True

    def test_suspended_false(self):
        """Suspend flag False returns False."""
        assert self.checker.check_suspension(False) is False


class TestChasingRiskAssessment:
    """Test chasing risk assessment (追高风险)."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_high_risk_above_30pct_ma20(self):
        """Price 30%+ above MA20 is high risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("130.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=0
        )
        assert result == "high"

    def test_high_risk_5_consecutive_gains(self):
        """5+ consecutive gains is high risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("100.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=5
        )
        assert result == "high"

    def test_medium_risk_above_15pct_ma20(self):
        """Price 15%+ above MA20 is medium risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("115.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=0
        )
        assert result == "medium"

    def test_medium_risk_3_consecutive_gains(self):
        """3+ consecutive gains is medium risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("100.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=3
        )
        assert result == "medium"

    def test_low_risk_below_thresholds(self):
        """Below all thresholds is low risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("100.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=0
        )
        assert result == "low"

    def test_low_risk_2_consecutive_gains(self):
        """2 consecutive gains is still low risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("100.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=2
        )
        assert result == "low"

    def test_high_risk_boundary_exactly_30pct(self):
        """Exactly 30% above MA20 is high risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("130.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=0
        )
        assert result == "high"

    def test_medium_risk_boundary_exactly_15pct(self):
        """Exactly 15% above MA20 is medium risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("115.00"),
            ma20=Decimal("100.00"),
            consecutive_gains=0
        )
        assert result == "medium"

    def test_zero_ma20_returns_low(self):
        """Zero MA20 returns low risk."""
        result = self.checker.check_chasing_risk(
            current_price=Decimal("100.00"),
            ma20=Decimal("0"),
            consecutive_gains=0
        )
        assert result == "low"


class TestConstraintEnforcement:
    """Test constraint enforcement with priority order."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_suspension_blocks_all(self):
        """Suspension (priority 1) blocks everything, returns position=0."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=True,
            chasing_risk="low"
        )
        assert position == Decimal("0")
        assert constraints == ["suspended"]

    def test_limit_up_blocks_buy(self):
        """Limit up (priority 2) blocks buy, returns position=0."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="limit_up",
            is_suspended=False,
            chasing_risk="low"
        )
        assert position == Decimal("0")
        assert constraints == ["limit_up_cannot_buy"]

    def test_limit_down_blocks_add(self):
        """Limit down (priority 3) blocks add position."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="limit_down",
            is_suspended=False,
            chasing_risk="low"
        )
        assert position == Decimal("0")
        assert constraints == ["limit_down_cannot_add"]

    def test_chasing_risk_high_reduces_position(self):
        """Chasing risk high (priority 4) reduces position by 50%."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=False,
            chasing_risk="high"
        )
        assert position == Decimal("50.00")
        assert constraints == ["chasing_risk_high"]

    def test_chasing_risk_medium_no_effect(self):
        """Chasing risk medium has no effect."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=False,
            chasing_risk="medium"
        )
        assert position == Decimal("100.00")
        assert constraints == []

    def test_chasing_risk_low_no_effect(self):
        """Chasing risk low has no effect."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=False,
            chasing_risk="low"
        )
        assert position == Decimal("100.00")
        assert constraints == []

    def test_all_normal_returns_recommended(self):
        """All normal returns recommended position."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=False,
            chasing_risk="low"
        )
        assert position == Decimal("100.00")
        assert constraints == []

    def test_suspension_overrides_chasing_risk(self):
        """Suspension overrides chasing risk."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="normal",
            is_suspended=True,
            chasing_risk="high"
        )
        assert position == Decimal("0")
        assert constraints == ["suspended"]

    def test_limit_up_overrides_chasing_risk(self):
        """Limit up overrides chasing risk."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="limit_up",
            is_suspended=False,
            chasing_risk="high"
        )
        assert position == Decimal("0")
        assert constraints == ["limit_up_cannot_buy"]

    def test_zero_recommended_position(self):
        """Zero recommended position returns zero."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("0"),
            limit_status="normal",
            is_suspended=False,
            chasing_risk="low"
        )
        assert position == Decimal("0")
        assert constraints == []


class TestConstraintEnforcementCombined:
    """Test multiple constraints combined."""

    def setup_method(self):
        self.checker = ConstraintChecker()

    def test_limit_down_and_chasing_risk(self):
        """Limit down takes priority over chasing risk."""
        position, constraints = self.checker.enforce_constraints(
            recommended_position=Decimal("100.00"),
            limit_status="limit_down",
            is_suspended=False,
            chasing_risk="high"
        )
        # Limit down returns position=0, chasing risk not applied
        assert position == Decimal("0")
        assert "limit_down_cannot_add" in constraints
