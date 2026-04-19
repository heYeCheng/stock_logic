---
plan_id: STOCK-05
phase: 4
requirement: STOCK-05
title: Stock Market Radar
description: Implement individual stock market radar (technical + sentiment scores)
type: feature
estimated_effort: 1.5h
---

# Plan: STOCK-05 - Stock Market Radar

## Goal
Implement individual stock market radar that generates technical and sentiment scores from pure volume-price data.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-05 section)
- Models: src/market/models.py
- Dependencies: Phase 1 data infrastructure (daily quotes)

## Technical Indicators
- **MA alignment**: Price vs MA5/MA10/MA20
- **Volume trend**: 5-day avg vs 20-day avg
- **RSI**: 14-day RSI
- **MACD**: Signal line crossover

## Sentiment Indicators
- **Recent limit-ups**: Count in past 5 days
- **Dragon leader status**: Is this stock a leader?
- **Institutional buying**: Net institutional flow

## Tasks

### Task 1: Create StockMarketScore model
**File**: `src/market/models.py` (append)

```python
class StockMarketScore(Base):
    """Daily stock market score snapshot."""
    __tablename__ = "stock_market_scores"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    technical_score = Column(Numeric(7, 4))  # 0-1
    sentiment_score = Column(Numeric(7, 4))  # 0-1
    market_composite = Column(Numeric(7, 4))  # (technical + sentiment) / 2
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'snapshot_date'),
    )
```

### Task 2: Implement StockTechnicalCalculator
**File**: `src/market/stock_radar.py` (create)

```python
from decimal import Decimal
from typing import List, Optional

class StockTechnicalCalculator:
    """Calculate stock technical scores."""
    
    def calculate(
        self,
        quotes: List[QuoteData],
        snapshot_date: date
    ) -> Decimal:
        """
        Calculate technical score from price/volume data.
        
        Args:
            quotes: Historical quotes (at least 60 days)
            snapshot_date: Score date
        
        Returns:
            Technical score (0-1)
        """
        if len(quotes) < 60:
            return Decimal("0.5")  # Not enough data
        
        # MA alignment (price vs MA5/10/20)
        ma_score = self._ma_alignment_score(quotes)
        
        # Volume trend
        volume_score = self._volume_trend_score(quotes)
        
        # RSI
        rsi_score = self._rsi_score(quotes)
        
        # MACD
        macd_score = self._macd_score(quotes)
        
        # Weighted average
        return (
            ma_score * Decimal("0.3") +
            volume_score * Decimal("0.25") +
            rsi_score * Decimal("0.25") +
            macd_score * Decimal("0.2")
        )
    
    def _ma_alignment_score(self, quotes: List[QuoteData]) -> Decimal:
        """Score based on MA alignment."""
        latest = quotes[-1]
        ma5 = self._calculate_ma(quotes, 5)
        ma10 = self._calculate_ma(quotes, 10)
        ma20 = self._calculate_ma(quotes, 20)
        
        price = Decimal(str(latest.close))
        
        # Bullish: price > ma5 > ma10 > ma20
        if price > ma5 > ma10 > ma20:
            return Decimal("1.0")
        # Bearish: price < ma5 < ma10 < ma20
        elif price < ma5 < ma10 < ma20:
            return Decimal("0")
        else:
            # Partial alignment
            score = Decimal("0.5")
            if price > ma5:
                score += Decimal("0.125")
            if ma5 > ma10:
                score += Decimal("0.125")
            if ma10 > ma20:
                score += Decimal("0.125")
            return min(score, Decimal("1.0"))
    
    def _volume_trend_score(self, quotes: List[QuoteData]) -> Decimal:
        """Score based on volume trend."""
        vol_5 = sum(q.volume for q in quotes[-5:]) / 5
        vol_20 = sum(q.volume for q in quotes[-20:]) / 20
        
        if vol_20 == 0:
            return Decimal("0.5")
        
        ratio = Decimal(str(vol_5 / vol_20))
        
        if ratio > Decimal("1.5"):
            return Decimal("1.0")  # Strong volume
        elif ratio > Decimal("1.0"):
            return Decimal("0.75")
        elif ratio > Decimal("0.8"):
            return Decimal("0.5")
        else:
            return Decimal("0.25")
    
    def _rsi_score(self, quotes: List[QuoteData]) -> Decimal:
        """Score based on RSI."""
        rsi = self._calculate_rsi(quotes, 14)
        
        if rsi > 70:
            return Decimal("0.8")  # Overbought but strong
        elif rsi > 50:
            return Decimal("0.6")  # Bullish
        elif rsi > 30:
            return Decimal("0.4")  # Neutral
        else:
            return Decimal("0.2")  # Oversold but weak
    
    def _macd_score(self, quotes: List[QuoteData]) -> Decimal:
        """Score based on MACD."""
        macd_line, signal_line = self._calculate_macd(quotes)
        
        if macd_line > signal_line and macd_line > 0:
            return Decimal("1.0")  # Bullish crossover above zero
        elif macd_line > signal_line:
            return Decimal("0.75")  # Bullish crossover below zero
        elif macd_line < signal_line and macd_line < 0:
            return Decimal("0")  # Bearish below zero
        else:
            return Decimal("0.25")  # Bearish above zero
```

### Task 3: Implement StockSentimentCalculator
**File**: `src/market/stock_radar.py` (append)

```python
class StockSentimentCalculator:
    """Calculate stock sentiment scores."""
    
    def calculate(
        self,
        stock_code: str,
        snapshot_date: date,
        limit_ups: int,
        is_dragon: bool,
        institutional_flow: Decimal
    ) -> Decimal:
        """
        Calculate sentiment score.
        
        Args:
            stock_code: Stock code
            snapshot_date: Score date
            limit_ups: Count of limit-ups in past 5 days
            is_dragon: Is this stock a dragon leader?
            institutional_flow: Net institutional flow
        
        Returns:
            Sentiment score (0-1)
        """
        # Limit-up frequency (0-5)
        limit_score = min(Decimal(str(limit_ups)) / Decimal("5"), Decimal("1.0"))
        
        # Dragon leader bonus
        dragon_score = Decimal("1.0") if is_dragon else Decimal("0.5")
        
        # Institutional flow
        if institutional_flow > 0:
            flow_score = min(institutional_flow / Decimal("1000000"), Decimal("1.0"))
        else:
            flow_score = Decimal("0")
        
        # Weighted average
        return (
            limit_score * Decimal("0.4") +
            dragon_score * Decimal("0.35") +
            flow_score * Decimal("0.25")
        )
```

### Task 4: Create StockRadarService
**File**: `src/market/stock_radar.py` (append)

```python
class StockRadarService:
    """Generate daily stock market radar snapshots."""
    
    def __init__(self):
        self.technical_calc = StockTechnicalCalculator()
        self.sentiment_calc = StockSentimentCalculator()
    
    async def generate_snapshot(
        self,
        stock_code: str,
        snapshot_date: date
    ) -> StockMarketScore:
        """Generate market score snapshot for a stock."""
        
        # Get quotes
        quotes = await self._get_quotes(stock_code, snapshot_date)
        
        # Get sentiment data
        limit_ups = await self._get_limit_up_count(stock_code, snapshot_date)
        is_dragon = await self._is_dragon_leader(stock_code)
        inst_flow = await self._get_institutional_flow(stock_code, snapshot_date)
        
        # Calculate scores
        technical = self.technical_calc.calculate(quotes, snapshot_date)
        sentiment = self.sentiment_calc.calculate(
            stock_code, snapshot_date, limit_ups, is_dragon, inst_flow
        )
        composite = (technical + sentiment) / 2
        
        # Persist
        score = StockMarketScore(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            technical_score=technical,
            sentiment_score=sentiment,
            market_composite=composite
        )
        
        await self._persist(score)
        return score
```

### Task 5: Create Alembic migration
**File**: `alembic/versions/xxxx_add_stock_market_scores.py` (create)

```python
def upgrade() -> None:
    op.create_table('stock_market_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(20), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('technical_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('sentiment_score', sa.Numeric(7, 4), nullable=True),
        sa.Column('market_composite', sa.Numeric(7, 4), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'snapshot_date')
    )
    
    op.create_index('idx_stock', 'stock_market_scores', ['stock_code'])
    op.create_index('idx_date', 'stock_market_scores', ['snapshot_date'])
```

### Task 6: Create unit tests
**File**: `tests/test_stock_radar.py`

Test cases:
- Technical score calculation (MA alignment)
- Technical score calculation (volume trend)
- Technical score calculation (RSI, MACD)
- Sentiment score calculation
- Composite score aggregation
- Snapshot persistence

## Success Criteria
- [ ] StockTechnicalCalculator implements all indicators
- [ ] StockSentimentCalculator works
- [ ] StockRadarService generates snapshots
- [ ] StockMarketScore model created
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- INFRA-01: Database models (completed)
- Phase 1: Daily quotes data (completed)

## Notes
- Technical indicators standard (MA, RSI, MACD, volume)
- Sentiment includes limit-ups and institutional flow
- Composite = (technical + sentiment) / 2
