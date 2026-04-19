---
plan_id: MARKET-01
phase: 4
requirement: MARKET-01
title: Sector Market Radar
description: Implement sector technical and sentiment scoring from pure volume-price data
type: feature
estimated_effort: 2h
---

# Plan: MARKET-01 - Sector Market Radar

## Goal
Implement sector market radar that generates technical and sentiment scores based purely on volume-price data, independent from logic scores.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (MARKET-01 section)
- Models: src/market/models.py (to be created)
- Dependencies: Phase 1 data infrastructure, Tushare daily quotes

## Technical Score Components

```python
def calculate_technical_score(sector_stocks: List[Stock], snapshot_date: date) -> Decimal:
    """
    Calculate sector technical score from component stocks.
    
    Components:
    - Trend strength: 20-day vs 60-day MA slope
    - Momentum: RSI, MACD histogram
    - Volume: 5-day avg vs 20-day avg
    - Volatility: ATR normalized
    
    Returns: 0-1 score
    """
```

## Sentiment Score Components

```python
def calculate_sentiment_score(sector_stocks: List[Stock], snapshot_date: date) -> Decimal:
    """
    Calculate sector sentiment score.
    
    Components:
    - Limit board frequency: Count of limit-up stocks
    - Dragon leader presence
    - Continuity: Consecutive positive days
    - Breadth: % of stocks above MA20
    
    Returns: 0-1 score
    """
```

## Tasks

### Task 1: Create SectorScore model
**File**: `src/market/models.py` (create)

```python
class SectorScore(Base):
    __tablename__ = "sector_scores"
    
    id = Column(Integer, primary_key=True)
    sector_id = Column(String(50), nullable=False, index=True)
    sector_name = Column(String(100))
    snapshot_date = Column(Date, nullable=False, index=True)
    technical_score = Column(Numeric(7, 4))
    sentiment_score = Column(Numeric(7, 4))
    composite_score = Column(Numeric(7, 4))
    state = Column(String(20))  # weak/normal/overheated
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('sector_id', 'snapshot_date'),
    )
```

### Task 2: Implement TechnicalScoreCalculator
**File**: `src/market/sector_radar.py` (create)

```python
class TechnicalScoreCalculator:
    """Calculate technical scores from volume-price data."""
    
    def __init__(self, config: TechnicalConfig):
        self.config = config
    
    def calculate(self, stocks: List[StockData], snapshot_date: date) -> Decimal:
        """Calculate technical score for a basket of stocks."""
        
        # Trend strength (MA slope)
        trend_scores = [self._ma_slope_score(s) for s in stocks]
        
        # Momentum (RSI, MACD)
        momentum_scores = [self._momentum_score(s) for s in stocks]
        
        # Volume trend
        volume_scores = [self._volume_score(s) for s in stocks]
        
        # Aggregate
        return self._aggregate(trend_scores, momentum_scores, volume_scores)
```

### Task 3: Implement SentimentScoreCalculator
**File**: `src/market/sector_radar.py` (append)

```python
class SentimentScoreCalculator:
    """Calculate sentiment scores from market behavior."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
    
    def calculate(self, stocks: List[StockData], snapshot_date: date) -> Decimal:
        """Calculate sentiment score for a basket of stocks."""
        
        # Limit board frequency
        limit_count = self._count_limit_ups(stocks, snapshot_date)
        
        # Dragon leader presence
        has_dragon = self._has_dragon_leader(stocks)
        
        # Continuity
        continuity = self._measure_continuity(stocks)
        
        # Breadth
        breadth = self._measure_breadth(stocks)
        
        return self._aggregate(limit_count, has_dragon, continuity, breadth)
```

### Task 4: Create SectorRadarService
**File**: `src/market/sector_radar.py` (append)

```python
class SectorRadarService:
    """Generate daily sector radar snapshots."""
    
    def __init__(self):
        self.technical_calc = TechnicalScoreCalculator(TechnicalConfig())
        self.sentiment_calc = SentimentScoreCalculator(SentimentConfig())
    
    async def generate_snapshot(self, sector_id: str, snapshot_date: date) -> SectorScore:
        """Generate snapshot for a sector."""
        
        # Get sector constituents
        stocks = await self._get_sector_stocks(sector_id)
        
        # Calculate scores
        technical = self.technical_calc.calculate(stocks, snapshot_date)
        sentiment = self.sentiment_calc.calculate(stocks, snapshot_date)
        composite = (technical + sentiment) / 2
        
        # Determine state
        state = self._determine_state(composite)
        
        # Persist
        score = SectorScore(
            sector_id=sector_id,
            sector_name=stocks[0].sector_name if stocks else "",
            snapshot_date=snapshot_date,
            technical_score=technical,
            sentiment_score=sentiment,
            composite_score=composite,
            state=state.value
        )
        
        await self._persist(score)
        return score
```

### Task 5: Create unit tests
**File**: `tests/test_sector_radar.py`

Test cases:
- Technical score calculation (individual components)
- Sentiment score calculation (individual components)
- Composite score aggregation
- State determination (weak/normal/overheated)
- Sector snapshot persistence
- Empty sector handling

## Success Criteria
- [ ] SectorScore model created with migrations
- [ ] TechnicalScoreCalculator implements all components
- [ ] SentimentScoreCalculator implements all components
- [ ] SectorRadarService generates daily snapshots
- [ ] State determination works correctly
- [ ] Unit tests pass

## Dependencies
- INFRA-01: Database models (completed)
- INFRA-03: Tushare data access (completed)
- Phase 3: Logic layer (for reference, not dependency)

## Notes
- Technical and sentiment scores are 0-1 scale
- Composite = (technical + sentiment) / 2
- State determination in MARKET-02
