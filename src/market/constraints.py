"""A-share trading constraint enforcement service.

EXEC-02: Enforce A-share specific trading rules (limit up/down, suspension, chasing risk)
"""

from decimal import Decimal
from typing import List, Tuple, Optional
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from src.market.models import ConstraintCheck


class ConstraintChecker:
    """Check and enforce A-share trading constraints."""

    # Limit thresholds by market
    LIMIT_MAIN = Decimal("0.10")   # Main board +/-10%
    LIMIT_ST = Decimal("0.05")     # ST stocks +/-5%
    LIMIT_STAR = Decimal("0.20")   # STAR Market +/-20%

    # Chasing risk thresholds
    CHASING_HIGH_MA = Decimal("1.30")   # 30% above MA20
    CHASING_MEDIUM_MA = Decimal("1.15") # 15% above MA20
    CHASING_HIGH_GAINS = 5              # Consecutive gains
    CHASING_MEDIUM_GAINS = 3

    def get_limit_threshold(self, stock_code: str) -> Decimal:
        """Get limit threshold based on stock type.

        Args:
            stock_code: Stock code (e.g., "000001.SZ", "688xxx", "STxxx")

        Returns:
            Limit threshold decimal (0.05, 0.10, or 0.20)
        """
        # Check if ST stock
        if "ST" in stock_code.upper():
            return self.LIMIT_ST
        # Check if STAR Market (688xxx)
        if stock_code.startswith("688"):
            return self.LIMIT_STAR
        return self.LIMIT_MAIN

    def check_limit_status(
        self,
        stock_code: str,
        current_price: Decimal,
        prev_close: Decimal
    ) -> str:
        """Check if stock is at limit up or limit down.

        Args:
            stock_code: Stock code for determining threshold
            current_price: Current trading price
            prev_close: Previous closing price

        Returns:
            "limit_up" | "limit_down" | "normal"
        """
        if prev_close == 0:
            return "normal"

        change_pct = (current_price - prev_close) / prev_close
        threshold = self.get_limit_threshold(stock_code)

        # Small tolerance for floating point
        tolerance = Decimal("0.001")

        if change_pct >= threshold - tolerance:
            return "limit_up"
        elif change_pct <= -threshold + tolerance:
            return "limit_down"
        else:
            return "normal"

    def check_suspension(self, suspend_flag: bool) -> bool:
        """Check if stock is suspended.

        Args:
            suspend_flag: From Tushare suspend_status API

        Returns:
            True if suspended
        """
        return suspend_flag

    def check_chasing_risk(
        self,
        current_price: Decimal,
        ma20: Decimal,
        consecutive_gains: int
    ) -> str:
        """Assess chasing risk (追高风险).

        Args:
            current_price: Current stock price
            ma20: 20-day moving average
            consecutive_gains: Number of consecutive gaining days

        Returns:
            "high" | "medium" | "low"
        """
        # Check price vs MA20
        if ma20 > 0:
            price_ratio = current_price / ma20
        else:
            price_ratio = Decimal("1")

        # High risk: 30% above MA20 or 5+ consecutive gains
        if price_ratio > self.CHASING_HIGH_MA or consecutive_gains >= self.CHASING_HIGH_GAINS:
            return "high"

        # Medium risk: 15% above MA20 or 3+ consecutive gains
        elif price_ratio > self.CHASING_MEDIUM_MA or consecutive_gains >= self.CHASING_MEDIUM_GAINS:
            return "medium"

        else:
            return "low"

    def enforce_constraints(
        self,
        recommended_position: Decimal,
        limit_status: str,
        is_suspended: bool,
        chasing_risk: str
    ) -> Tuple[Decimal, List[str]]:
        """Apply constraints in priority order.

        Priority:
        1. Suspension (hard block) - position = 0
        2. Limit up (cannot buy) - position = 0
        3. Limit down (cannot add) - position = 0
        4. Chasing risk high (soft reduction) - position *= 0.5

        Args:
            recommended_position: Original recommended position size
            limit_status: Limit status from check_limit_status
            is_suspended: Suspension flag
            chasing_risk: Chasing risk level

        Returns:
            (final_position, list of applied constraint codes)
        """
        constraints = []
        position = recommended_position

        # Priority 1: Suspension (hard block)
        if is_suspended:
            return Decimal("0"), ["suspended"]

        # Priority 2: Limit up (cannot buy)
        if limit_status == "limit_up":
            return Decimal("0"), ["limit_up_cannot_buy"]

        # Priority 3: Limit down (cannot add)
        if limit_status == "limit_down":
            if position > 0:
                position = Decimal("0")
                constraints.append("limit_down_cannot_add")

        # Priority 4: Chasing risk (soft reduction)
        if chasing_risk == "high":
            position = position * Decimal("0.5")
            constraints.append("chasing_risk_high")

        return position, constraints


class ConstraintService:
    """Manage constraint check snapshots."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.checker = ConstraintChecker()

    async def check_all_constraints(
        self,
        snapshot_date: date
    ) -> List[ConstraintCheck]:
        """Check constraints for all stocks.

        Args:
            snapshot_date: Date for the constraint check

        Returns:
            List of ConstraintCheck objects
        """
        # Get stock data - placeholder for actual stock data fetch
        # In production, this would fetch from Tushare or other data source
        stocks = await self._get_stock_data(snapshot_date)

        checks = []

        for stock in stocks:
            # Check limit status
            limit_status = self.checker.check_limit_status(
                stock.ts_code, stock.close, stock.prev_close
            )

            # Check suspension
            is_suspended = self.checker.check_suspension(
                stock.suspend_flag
            )

            # Check chasing risk
            chasing_risk = self.checker.check_chasing_risk(
                stock.close, stock.ma20, stock.consecutive_gains
            )

            check = ConstraintCheck(
                stock_code=stock.ts_code,
                snapshot_date=snapshot_date,
                limit_status=limit_status,
                is_suspended=is_suspended,
                chasing_risk_level=chasing_risk,
                applied_constraints=[],  # Will be filled during enforcement
            )

            checks.append(check)

        # Persist
        await self._persist_batch(checks)
        return checks

    async def _get_stock_data(self, snapshot_date: date) -> List:
        """Fetch stock data for constraint checking.

        This is a placeholder - actual implementation would fetch from data source.
        """
        # Placeholder - returns empty list
        # Actual implementation would integrate with stock data service
        return []

    async def _persist_batch(self, checks: List[ConstraintCheck]) -> None:
        """Persist constraint checks to database."""
        for check in checks:
            self.session.add(check)
        await self.session.commit()

    async def apply_constraints_to_position(
        self,
        stock_code: str,
        recommended_position: Decimal
    ) -> Tuple[Decimal, List[str]]:
        """Apply constraints to a position recommendation.

        Args:
            stock_code: Stock code to check
            recommended_position: Recommended position size

        Returns:
            (final_position, applied_constraints)
        """
        # Get constraint check
        check = await self._get_constraint_check(stock_code, date.today())

        if not check:
            return recommended_position, []

        return self.checker.enforce_constraints(
            recommended_position,
            check.limit_status,
            check.is_suspended,
            check.chasing_risk_level
        )

    async def _get_constraint_check(
        self,
        stock_code: str,
        check_date: date
    ) -> Optional[ConstraintCheck]:
        """Get constraint check for a stock on a specific date."""
        stmt = select(ConstraintCheck).where(
            and_(
                ConstraintCheck.stock_code == stock_code,
                ConstraintCheck.snapshot_date == check_date
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
