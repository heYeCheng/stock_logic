---
plan_id: EXEC-02
phase: 5
requirement: EXEC-02
title: A-Share Trading Constraints
description: Enforce A-share specific trading rules (limit up/down, suspension, chasing risk)
type: feature
estimated_effort: 1h
---

# Plan: EXEC-02 - A-Share Trading Constraints

## Goal
Implement A-share specific trading constraint enforcement that overrides position recommendations when rules are triggered.

## Context
- Research: `.planning/phases/phase-5/RESEARCH.md` (EXEC-02 section)
- Models: `src/market/models.py`
- Dependencies: Phase 1 (stock data), Phase 4 (market radar)

## Constraints

| Constraint | Type | Effect |
|------------|------|--------|
| Limit Up | Hard | Cannot buy |
| Limit Down | Hard | Cannot add position |
| Suspension | Hard | Cannot buy or sell |
| Chasing Risk (high) | Soft | Reduce position 50% |

## Tasks

### Task 1: Create ConstraintCheck model
**File**: `src/market/models.py` (append)

```python
class ConstraintCheck(Base):
    """Daily constraint check results for a stock."""
    __tablename__ = "constraint_checks"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    limit_status = Column(String(20))  # limit_up/limit_down/normal
    is_suspended = Column(Boolean, default=False)
    chasing_risk_level = Column(String(20))  # high/medium/low
    applied_constraints = Column(Text)  # JSON array of constraint codes
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Create ConstraintChecker service
**File**: `src/market/constraints.py` (create)

```python
from decimal import Decimal
from typing import List, Tuple

class ConstraintChecker:
    """Check and enforce A-share trading constraints."""
    
    # Limit thresholds by market
    LIMIT_MAIN = Decimal("0.10")   # Main board ±10%
    LIMIT_ST = Decimal("0.05")     # ST stocks ±5%
    LIMIT_STAR = Decimal("0.20")   # STAR Market ±20%
    
    # Chasing risk thresholds
    CHASING_HIGH_MA = Decimal("1.30")   # 30% above MA20
    CHASING_MEDIUM_MA = Decimal("1.15") # 15% above MA20
    CHASING_HIGH_GAINS = 5              # Consecutive gains
    CHASING_MEDIUM_GAINS = 3
    
    def get_limit_threshold(self, stock_code: str) -> Decimal:
        """Get limit threshold based on stock type."""
        # Check if ST stock
        if "ST" in stock_code:
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
        """
        Check if stock is at limit up or limit down.
        
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
        """
        Check if stock is suspended.
        
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
        """
        Assess chasing risk (追高风险).
        
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
        """
        Apply constraints in priority order.
        
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
```

### Task 3: Create ConstraintService
**File**: `src/market/constraints.py` (append)

```python
class ConstraintService:
    """Manage constraint check snapshots."""
    
    def __init__(self):
        self.checker = ConstraintChecker()
    
    async def check_all_constraints(
        self,
        snapshot_date: date
    ) -> List[ConstraintCheck]:
        """Check constraints for all stocks."""
        
        # Get stock data
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
    
    async def apply_constraints_to_position(
        self,
        stock_code: str,
        recommended_position: Decimal
    ) -> Tuple[Decimal, List[str]]:
        """
        Apply constraints to a position recommendation.
        
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
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_constraint_checks.py` (create)

```python
def upgrade() -> None:
    op.create_table('constraint_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('limit_status', sa.String(20), nullable=True),
        sa.Column('is_suspended', sa.Boolean(), nullable=True),
        sa.Column('chasing_risk_level', sa.String(20), nullable=True),
        sa.Column('applied_constraints', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'constraint_checks', ['stock_code'])
    op.create_index('idx_date', 'constraint_checks', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_constraints.py`

Test cases:
- Limit threshold detection (main/ST/STAR)
- Limit status check (up/down/normal)
- Suspension check
- Chasing risk (high/medium/low boundaries)
- Constraint enforcement (suspension blocks all)
- Constraint enforcement (limit up blocks buy)
- Constraint enforcement (chasing risk reduces 50%)
- Multiple constraints combined

## Success Criteria
- [ ] ConstraintChecker implements all checks
- [ ] Enforcement priority order correct
- [ ] ConstraintCheck model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 1: Stock quote data (close, prev_close, ma20)
- Phase 4: Consecutive gains data

## Notes
- Hard constraints (suspension, limit up) return position=0
- Soft constraints (chasing risk) reduce position by 50%
- Constraint codes stored for audit trail
