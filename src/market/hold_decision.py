"""Hold/Sell/Reduce decision service for position management.

EXEC-04: Stop-Loss and Hold Decision Rules
Implements consistent decision logic for managing stock positions.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.market.models import HoldDecision


class HoldDecisionMaker:
    """Make hold/sell/reduce decisions based on stop-loss and hold rules.

    Stop-Loss Rules (hard triggers):
    - Logic score < 0.3 -> Sell (core logic invalidated)
    - Price < entry x 0.92 -> Sell (8% hard stop-loss)
    - Catalyst expired + logic < 0.5 -> Sell (event thesis complete)

    Reduction Rules:
    - Sector state = weak -> Reduce 50% (sector-wide weakness)

    Hold Rules:
    - Logic score >= 0.7 -> Hold (strong logic intact)
    - Market score >= 0.7 -> Hold (market momentum positive)
    - Composite score >= 0.6 -> Hold (overall score supportive)

    Decision Priority: stop-loss > reduce > hold
    """

    # Thresholds
    LOGIC_STOP = Decimal("0.3")  # Sell if below
    LOGIC_STRONG = Decimal("0.7")  # Hold if above
    LOGIC_CATALYST_THRESHOLD = Decimal("0.5")  # Catalyst expiration check
    MARKET_STRONG = Decimal("0.7")  # Hold if above
    COMPOSITE_HOLD = Decimal("0.6")  # Hold if above
    STOP_LOSS_PCT = Decimal("0.92")  # 8% stop-loss

    def check_logic_stop(self, logic_score: Decimal) -> Tuple[bool, str]:
        """Check if logic score triggers stop-loss.

        Args:
            logic_score: The logic layer score (0.0-1.0)

        Returns:
            (triggered, reason) - True if stop-loss should trigger
        """
        if logic_score < self.LOGIC_STOP:
            return True, f"逻辑分 ({logic_score}) 低于阈值"
        return False, ""

    def check_price_stop(
        self, entry_price: Decimal, current_price: Decimal
    ) -> Tuple[bool, str]:
        """Check if price triggers stop-loss.

        Args:
            entry_price: Average entry price
            current_price: Current market price

        Returns:
            (triggered, reason) - True if stop-loss should trigger
        """
        if current_price < entry_price * self.STOP_LOSS_PCT:
            pnl = (current_price - entry_price) / entry_price
            return True, f"价格止损 ({pnl:.1%})"
        return False, ""

    def check_catalyst_expired(
        self, catalyst_active: bool, logic_score: Decimal
    ) -> Tuple[bool, str]:
        """Check if catalyst expiration triggers sell.

        Args:
            catalyst_active: Whether catalyst is still active
            logic_score: The logic layer score

        Returns:
            (triggered, reason) - True if sell should trigger
        """
        if not catalyst_active and logic_score < self.LOGIC_CATALYST_THRESHOLD:
            return True, "催化剂失效且逻辑分不足"
        return False, ""

    def check_sector_weak(self, sector_state: str) -> Tuple[bool, str]:
        """Check if sector weakness triggers reduction.

        Args:
            sector_state: Current sector state (weak/normal/overheated)

        Returns:
            (triggered, reason) - True if reduction should trigger
        """
        if sector_state == "weak":
            return True, "板块弱势"
        return False, ""

    def check_hold_signals(
        self, logic_score: Decimal, market_score: Decimal, composite_score: Decimal
    ) -> Tuple[bool, str]:
        """Check if any hold signal is active.

        Args:
            logic_score: The logic layer score
            market_score: The market layer score
            composite_score: The combined composite score

        Returns:
            (triggered, reason) - True if hold signal is active
        """
        if logic_score >= self.LOGIC_STRONG:
            return True, f"强逻辑分 ({logic_score})"
        if market_score >= self.MARKET_STRONG:
            return True, f"强市场分 ({market_score})"
        if composite_score >= self.COMPOSITE_HOLD:
            return True, f"综合分 ({composite_score}) 支持持有"
        return False, ""

    def make_decision(
        self,
        current_position: Decimal,
        logic_score: Decimal,
        market_score: Decimal,
        composite_score: Decimal,
        entry_price: Decimal,
        current_price: Decimal,
        sector_state: str,
        catalyst_active: bool,
    ) -> Tuple[str, Decimal, str]:
        """Make hold/sell/reduce decision.

        Decision priority: stop-loss > reduce > hold

        Args:
            current_position: Current held position size
            logic_score: Logic layer score (0.0-1.0)
            market_score: Market layer score (0.0-1.0)
            composite_score: Combined score (0.0-1.0)
            entry_price: Average entry price
            current_price: Current market price
            sector_state: Sector state (weak/normal/overheated)
            catalyst_active: Whether catalyst is active

        Returns:
            (action, recommended_position, reason)
            action: "hold" | "sell" | "reduce"
        """
        # Calculate P&L
        pnl_pct = (
            (current_price - entry_price) / entry_price if entry_price > 0 else Decimal("0")
        )

        # Check stop-loss triggers (sell) - highest priority
        logic_stop, logic_reason = self.check_logic_stop(logic_score)
        if logic_stop:
            return "sell", Decimal("0"), logic_reason

        price_stop, price_reason = self.check_price_stop(entry_price, current_price)
        if price_stop:
            return "sell", Decimal("0"), price_reason

        catalyst_stop, catalyst_reason = self.check_catalyst_expired(
            catalyst_active, logic_score
        )
        if catalyst_stop:
            return "sell", Decimal("0"), catalyst_reason

        # Check reduction triggers - medium priority
        sector_weak, sector_reason = self.check_sector_weak(sector_state)
        if sector_weak:
            new_position = current_position * Decimal("0.5")
            return "reduce", new_position, sector_reason

        # Check hold triggers - default/fallback
        hold_signal, hold_reason = self.check_hold_signals(
            logic_score, market_score, composite_score
        )
        if hold_signal:
            return "hold", current_position, hold_reason

        # Default: hold if no strong signal
        return "hold", current_position, "无明确信号，默认持有"


class HoldDecisionService:
    """Manage hold decision snapshots."""

    def __init__(self):
        self.decision_maker = HoldDecisionMaker()

    async def _get_current_positions(
        self, snapshot_date: date
    ) -> List[object]:
        """Get stocks with current positions.

        TODO: Implement position tracking query.
        For now, returns empty list as placeholder.
        """
        # TODO: Query positions table when implemented
        return []

    async def _get_stock_scores(
        self, stock_code: str, snapshot_date: date
    ) -> dict:
        """Get scores for a specific stock.

        Args:
            stock_code: Stock code (e.g., "000001.SZ")
            snapshot_date: Date of score snapshot

        Returns:
            Dict with logic_score, market_score, composite_score, sector_state, catalyst_active
        """
        # TODO: Query stock_composite_scores, stock_market_scores, sector_scores, stock_catalysts
        return {
            "logic_score": Decimal("0.5"),
            "market_score": Decimal("0.5"),
            "composite_score": Decimal("0.5"),
            "sector_state": "normal",
            "catalyst_active": True,
        }

    async def _persist_batch(self, decisions: List[HoldDecision]) -> None:
        """Persist batch of decisions to database.

        Args:
            decisions: List of HoldDecision objects to persist
        """
        async with async_session_maker() as session:
            for decision in decisions:
                session.add(decision)
            await session.commit()

    async def generate_decisions(self, snapshot_date: date) -> List[HoldDecision]:
        """Generate hold decisions for all stocks with positions.

        Args:
            snapshot_date: Date for which to generate decisions

        Returns:
            List of HoldDecision objects
        """
        # Get stocks with current positions
        positions = await self._get_current_positions(snapshot_date)

        decisions = []

        for position in positions:
            # Get scores
            scores = await self._get_stock_scores(position.stock_code, snapshot_date)

            action, new_position, reason = self.decision_maker.make_decision(
                current_position=position.size,
                logic_score=scores["logic_score"],
                market_score=scores["market_score"],
                composite_score=scores["composite_score"],
                entry_price=position.entry_price,
                current_price=position.current_price,
                sector_state=scores["sector_state"],
                catalyst_active=scores["catalyst_active"],
            )

            pnl_pct = (
                (position.current_price - position.entry_price) / position.entry_price
                if position.entry_price > 0
                else Decimal("0")
            )

            decision = HoldDecision(
                stock_code=position.stock_code,
                snapshot_date=snapshot_date,
                current_position=position.size,
                action=action,
                recommended_position=new_position,
                action_reason=reason,
                entry_price=position.entry_price,
                current_price=position.current_price,
                pnl_pct=pnl_pct,
            )

            decisions.append(decision)

        # Persist
        await self._persist_batch(decisions)
        return decisions

    async def get_decision(
        self, stock_code: str, snapshot_date: date
    ) -> Optional[HoldDecision]:
        """Get decision for a specific stock.

        Args:
            stock_code: Stock code (e.g., "000001.SZ")
            snapshot_date: Date of decision

        Returns:
            HoldDecision or None if not found
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(HoldDecision).where(
                    HoldDecision.stock_code == stock_code,
                    HoldDecision.snapshot_date == snapshot_date,
                )
            )
            return result.scalar_one_or_none()
