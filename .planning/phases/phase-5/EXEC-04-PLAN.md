---
plan_id: EXEC-04
phase: 5
requirement: EXEC-04
title: Stop-Loss and Hold Decisions
description: Implement consistent stop-loss and hold decision rules
type: feature
estimated_effort: 0.5h
---

# Plan: EXEC-04 - Stop-Loss and Hold Decisions

## Goal
Implement stop-loss and hold decision rules for position management.

## Context
- Research: `.planning/phases/phase-5/RESEARCH.md` (EXEC-04 section)
- Models: `src/market/models.py`
- Dependencies: Phase 4 (composite scores, sector states, catalyst levels)

## Stop-Loss Rules

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Logic score < 0.3 | Sell | Core logic invalidated |
| Price < entry × 0.92 | Sell | 8% hard stop-loss |
| Sector state = weak | Reduce 50% | Sector-wide weakness |
| Catalyst expired + logic < 0.5 | Sell | Event thesis complete |

## Hold Rules

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Logic score ≥ 0.7 | Hold | Strong logic intact |
| Market score ≥ 0.7 | Hold | Market momentum positive |
| Composite ≥ 0.6 | Hold | Overall score supportive |

## Tasks

### Task 1: Create HoldDecision model
**File**: `src/market/models.py` (append)

```python
class HoldDecision(Base):
    """Daily hold/sell/reduce decision for a stock."""
    __tablename__ = "hold_decisions"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    current_position = Column(Numeric(7, 4))  # Current held position
    action = Column(String(20))  # hold/sell/reduce
    recommended_position = Column(Numeric(7, 4))
    action_reason = Column(Text)  # Explanation of decision
    entry_price = Column(Numeric(10, 4))  # Average entry price
    current_price = Column(Numeric(10, 4))
    pnl_pct = Column(Numeric(7, 4))  # P&L percentage
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create HoldDecisionMaker service
**File**: `src/market/hold_decision.py` (create)

```python
from decimal import Decimal
from typing import Tuple

class HoldDecisionMaker:
    """Make hold/sell/reduce decisions."""
    
    # Thresholds
    LOGIC_STOP = Decimal("0.3")      # Sell if below
    LOGIC_STRONG = Decimal("0.7")    # Hold if above
    MARKET_STRONG = Decimal("0.7")   # Hold if above
    COMPOSITE_HOLD = Decimal("0.6")  # Hold if above
    STOP_LOSS_PCT = Decimal("0.92")  # 8% stop-loss
    
    def check_logic_stop(self, logic_score: Decimal) -> Tuple[bool, str]:
        """Check if logic score triggers stop-loss."""
        if logic_score < self.LOGIC_STOP:
            return True, f"逻辑分 ({logic_score}) 低于阈值"
        return False, ""
    
    def check_price_stop(
        self,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str]:
        """Check if price triggers stop-loss."""
        if current_price < entry_price * self.STOP_LOSS_PCT:
            pnl = (current_price - entry_price) / entry_price
            return True, f"价格止损 ({pnl:.1%})"
        return False, ""
    
    def check_catalyst_expired(
        self,
        catalyst_active: bool,
        logic_score: Decimal
    ) -> Tuple[bool, str]:
        """Check if catalyst expiration triggers sell."""
        if not catalyst_active and logic_score < Decimal("0.5"):
            return True, "催化剂失效且逻辑分不足"
        return False, ""
    
    def check_sector_weak(
        self,
        sector_state: str
    ) -> Tuple[bool, str]:
        """Check if sector weakness triggers reduction."""
        if sector_state == "weak":
            return True, "板块弱势"
        return False, ""
    
    def check_hold_signals(
        self,
        logic_score: Decimal,
        market_score: Decimal,
        composite_score: Decimal
    ) -> Tuple[bool, str]:
        """Check if any hold signal is active."""
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
        catalyst_active: bool
    ) -> Tuple[str, Decimal, str]:
        """
        Make hold/sell/reduce decision.
        
        Returns:
            (action, recommended_position, reason)
            action: "hold" | "sell" | "reduce"
        """
        # Calculate P&L
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else Decimal("0")
        
        # Check stop-loss triggers (sell)
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
        
        # Check reduction triggers
        sector_weak, sector_reason = self.check_sector_weak(sector_state)
        if sector_weak:
            new_position = current_position * Decimal("0.5")
            return "reduce", new_position, sector_reason
        
        # Check hold triggers
        hold_signal, hold_reason = self.check_hold_signals(
            logic_score, market_score, composite_score
        )
        if hold_signal:
            return "hold", current_position, hold_reason
        
        # Default: hold if no strong signal
        return "hold", current_position, "无明确信号，默认持有"
```

### Task 3: Create HoldDecisionService
**File**: `src/market/hold_decision.py` (append)

```python
class HoldDecisionService:
    """Manage hold decision snapshots."""
    
    def __init__(self):
        self.decision_maker = HoldDecisionMaker()
    
    async def generate_decisions(
        self,
        snapshot_date: date
    ) -> List[HoldDecision]:
        """Generate hold decisions for all stocks with positions."""
        
        # Get stocks with current positions
        positions = await self._get_current_positions(snapshot_date)
        
        decisions = []
        
        for position in positions:
            # Get scores
            scores = await self._get_stock_scores(
                position.stock_code, snapshot_date
            )
            
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
                if position.entry_price > 0 else Decimal("0")
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
        self,
        stock_code: str,
        snapshot_date: date
    ) -> Optional[HoldDecision]:
        """Get decision for a specific stock."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(HoldDecision).where(
                    HoldDecision.stock_code == stock_code,
                    HoldDecision.snapshot_date == snapshot_date
                )
            )
            return result.scalar_one_or_none()
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_hold_decisions.py` (create)

```python
def upgrade() -> None:
    op.create_table('hold_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('current_position', sa.Numeric(7, 4), nullable=True),
        sa.Column('action', sa.String(20), nullable=True),
        sa.Column('recommended_position', sa.Numeric(7, 4), nullable=True),
        sa.Column('action_reason', sa.Text(), nullable=True),
        sa.Column('entry_price', sa.Numeric(10, 4), nullable=True),
        sa.Column('current_price', sa.Numeric(10, 4), nullable=True),
        sa.Column('pnl_pct', sa.Numeric(7, 4), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'hold_decisions', ['stock_code'])
    op.create_index('idx_date', 'hold_decisions', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_hold_decision.py`

Test cases:
- Logic stop-loss trigger
- Price stop-loss trigger (8% rule)
- Catalyst expiration sell
- Sector weakness reduction
- Hold signals (logic/market/composite)
- Decision priority (stop-loss > reduce > hold)
- P&L calculation

## Success Criteria
- [ ] HoldDecisionMaker implements all rules
- [ ] Decision priority correct
- [ ] HoldDecision model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 4: Composite scores, sector states, catalyst levels
- Position tracking (current positions, entry prices)

## Notes
- Stop-loss rules are hard triggers (sell all)
- Reduction rules cut position by 50%
- Hold rules maintain current position
- Default to hold when signals conflict (conservative)
