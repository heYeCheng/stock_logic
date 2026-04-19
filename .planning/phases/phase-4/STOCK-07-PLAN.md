---
plan_id: STOCK-07
phase: 4
requirement: STOCK-07
title: Dragon/Leader Identification
description: Implement dragon leader (龙头), zhongjun (中军), and follower (跟风) classification
type: feature
estimated_effort: 1.5h
---

# Plan: STOCK-07 - Dragon/Leader Identification

## Goal
Implement stock role identification within sectors: dragon leader (龙头), zhongjun (中军), and follower (跟风).

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-07 section)
- Models: src/market/models.py
- Dependencies: Phase 1 data (daily quotes), MARKET-05 (limit board data)

## Classification Criteria

```python
def identify_leader_role(stock, sector_stocks):
    """
    Classify stock's role within sector.
    """
    
    # Dragon leader: First to limit-up, highest consecutive gains
    dragon_score = (
        stock.limit_up_count * 2 +  # Weight limit-ups heavily
        stock.consecutive_gains +
        (1 if stock.is_first_limit else 0) * 3  # Bonus for being first
    )
    
    # Zhongjun: Large cap, stable gains, high volume
    zhongjun_score = (
        stock.market_cap_rank * 0.5 +  # Lower rank = larger cap
        stock.volume_stability +
        stock.trend_consistency
    )
    
    if dragon_score > threshold_dragon:
        return "dragon"
    elif zhongjun_score > threshold_zhongjun:
        return "zhongjun"
    else:
        return "follower"
```

## Tasks

### Task 1: Create StockLeaderRole model
**File**: `src/market/models.py` (append)

```python
class StockLeaderRole(Base):
    """Stock leader role classification."""
    __tablename__ = "stock_leader_roles"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    sector_id = Column(String(50), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    role = Column(String(20))  # dragon/zhongjun/follower
    dragon_score = Column(Numeric(7, 4))
    zhongjun_score = Column(Numeric(7, 4))
    confidence = Column(Float)
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'sector_id', 'snapshot_date'),
    )

class LeaderRole(str, Enum):
    dragon = "dragon"       # 龙头
    zhongjun = "zhongjun"   # 中军
    follower = "follower"   # 跟风
```

### Task 2: Create LeaderIdentificationService
**File**: `src/market/leader.py` (create)

```python
from decimal import Decimal
from typing import List, Tuple

class LeaderIdentificationService:
    """Identify stock leader roles within sectors."""
    
    # Thresholds
    DRAGON_THRESHOLD = Decimal("5.0")
    ZHONGJUN_THRESHOLD = Decimal("3.0")
    
    def calculate_dragon_score(
        self,
        stock: StockData,
        sector_stocks: List[StockData]
    ) -> Decimal:
        """
        Calculate dragon leader score.
        
        Factors:
        - Limit-up count (past 5 days)
        - Consecutive gains
        - First to limit-up bonus
        """
        # Limit-up count (weighted 2x)
        limit_up_score = Decimal(str(stock.limit_up_count or 0)) * Decimal("2")
        
        # Consecutive gains
        consecutive_score = Decimal(str(stock.consecutive_gains or 0))
        
        # First to limit-up bonus
        first_limit_bonus = Decimal("3") if stock.is_first_limit else Decimal("0")
        
        # Total
        return limit_up_score + consecutive_score + first_limit_bonus
    
    def calculate_zhongjun_score(
        self,
        stock: StockData,
        sector_stocks: List[StockData]
    ) -> Decimal:
        """
        Calculate zhongjun (anchor) score.
        
        Factors:
        - Market cap rank (lower = larger = better)
        - Volume stability
        - Trend consistency
        """
        # Market cap rank (invert: rank 1 = highest score)
        max_rank = len(sector_stocks)
        if stock.market_cap_rank and max_rank > 0:
            cap_score = Decimal(str((max_rank - stock.market_cap_rank + 1) / max_rank)) * Decimal("3")
        else:
            cap_score = Decimal("0")
        
        # Volume stability (low variance = high score)
        volume_stability = Decimal(str(stock.volume_stability or 0.5))
        volume_score = volume_stability * Decimal("2")
        
        # Trend consistency (MA alignment consistency)
        trend_consistency = Decimal(str(stock.trend_consistency or 0.5))
        trend_score = trend_consistency * Decimal("2")
        
        return cap_score + volume_score + trend_score
    
    def identify_role(
        self,
        stock: StockData,
        sector_stocks: List[StockData]
    ) -> Tuple[LeaderRole, Decimal, Decimal]:
        """
        Identify stock's role within sector.
        
        Returns:
            (role, dragon_score, zhongjun_score)
        """
        dragon_score = self.calculate_dragon_score(stock, sector_stocks)
        zhongjun_score = self.calculate_zhongjun_score(stock, sector_stocks)
        
        if dragon_score >= self.DRAGON_THRESHOLD:
            return LeaderRole.dragon, dragon_score, zhongjun_score
        elif zhongjun_score >= self.ZHONGJUN_THRESHOLD:
            return LeaderRole.zhongjun, dragon_score, zhongjun_score
        else:
            return LeaderRole.follower, dragon_score, zhongjun_score
    
    def calculate_confidence(
        self,
        role: LeaderRole,
        dragon_score: Decimal,
        zhongjun_score: Decimal
    ) -> float:
        """Calculate confidence in role assignment."""
        if role == LeaderRole.dragon:
            return float((dragon_score - self.DRAGON_THRESHOLD) / self.DRAGON_THRESHOLD)
        elif role == LeaderRole.zhongjun:
            return float((zhongjun_score - self.ZHONGJUN_THRESHOLD) / self.ZHONGJUN_THRESHOLD)
        else:
            # Follower - distance from thresholds
            dragon_dist = float(self.DRAGON_THRESHOLD - dragon_score)
            zhongjun_dist = float(self.ZHONGJUN_THRESHOLD - zhongjun_score)
            return min(dragon_dist, zhongjun_dist) / float(self.DRAGON_THRESHOLD)
```

### Task 3: Create LeaderService
**File**: `src/market/leader.py` (append)

```python
class LeaderService:
    """Manage leader role snapshots."""
    
    def __init__(self):
        self.identifier = LeaderIdentificationService()
    
    async def generate_snapshot(
        self,
        sector_id: str,
        snapshot_date: date
    ) -> List[StockLeaderRole]:
        """Generate leader role snapshots for all stocks in a sector."""
        
        # Get sector stocks
        stocks = await self._get_sector_stocks(sector_id)
        
        if not stocks:
            return []
        
        # Calculate roles
        roles = []
        for stock in stocks:
            role, dragon_score, zhongjun_score = self.identifier.identify_role(
                stock, stocks
            )
            confidence = self.identifier.calculate_confidence(
                role, dragon_score, zhongjun_score
            )
            
            record = StockLeaderRole(
                stock_code=stock.ts_code,
                sector_id=sector_id,
                snapshot_date=snapshot_date,
                role=role.value,
                dragon_score=dragon_score,
                zhongjun_score=zhongjun_score,
                confidence=confidence
            )
            
            roles.append(record)
        
        # Persist all
        await self._persist_batch(roles)
        return roles
```

### Task 4: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_leader_roles.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_leader_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('sector_id', sa.String(50), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('role', sa.String(20), nullable=True),
        sa.Column('dragon_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('zhongjun_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'sector_id', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'stock_leader_roles', ['stock_code'])
    op.create_index('idx_sector', 'stock_leader_roles', ['sector_id'])
    op.create_index('idx_date', 'stock_leader_roles', ['snapshot_date'])
```

### Task 5: Create unit tests
**File**: `tests/test_leader.py`

Test cases:
- Dragon score calculation (limit-ups)
- Dragon score calculation (consecutive gains)
- Zhongjun score calculation (market cap)
- Zhongjun score calculation (volume stability)
- Role identification (dragon threshold)
- Role identification (zhongjun threshold)
- Role identification (follower default)
- Confidence calculation

## Success Criteria
- [ ] LeaderIdentificationService calculates scores correctly
- [ ] Role thresholds work as expected
- [ ] StockLeaderRole model created
- [ ] LeaderService generates snapshots
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- Phase 1: Stock data (completed)
- MARKET-05: Limit board data (completed)

## Notes
- Dragon = aggressive leader (limit-ups, consecutive gains)
- Zhongjun = stable anchor (large cap, consistent)
- Follower = neither dragon nor zhongjun
- Confidence helps downstream layers assess reliability
