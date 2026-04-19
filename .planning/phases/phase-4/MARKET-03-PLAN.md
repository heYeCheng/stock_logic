---
plan_id: MARKET-03
phase: 4
requirement: MARKET-03
title: Lead Concentration Calculation
description: Implement HHI-based concentration measurement for sector leadership
type: feature
estimated_effort: 1.5h
---

# Plan: MARKET-03 - Lead Concentration Calculation

## Goal
Implement lead concentration calculation using Herfindahl-Hirschman Index (HHI) to measure if sector leadership is concentrated or diffuse.

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (MARKET-03 section)
- Models: src/market/models.py
- Dependencies: MARKET-01 (sector scores)

## HHI Formula

```python
def calculate_lead_concentration(stocks_in_sector: List[StockData]) -> Decimal:
    """
    Measures if leadership is concentrated in few stocks or diffuse.
    
    Uses Herfindahl-Hirschman Index (HHI) on strength scores.
    """
    strengths = [s.market_score for s in stocks_in_sector if s.is_leader_candidate]
    
    if not strengths:
        return Decimal("0")
    
    total = sum(strengths)
    if total == 0:
        return Decimal("0")
    
    # Calculate market shares
    shares = [Decimal(str(s / total)) for s in strengths]
    
    # HHI: sum of squared market shares
    hhi = sum(s ** 2 for s in shares)
    
    # Normalize to 0-1 (HHI ranges from 1/n to 1)
    n = len(strengths)
    min_hhi = Decimal(str(1 / n))
    normalized_hhi = (hhi - min_hhi) / (Decimal("1") - min_hhi)
    
    return normalized_hhi
```

## Interpretation
- **High concentration (>0.6)**: Leadership concentrated in few stocks (龙头带动)
- **Medium (0.3-0.6)**: Balanced leadership
- **Low (<0.3)**: Diffuse leadership, sector rotation (快速轮动)

## Tasks

### Task 1: Implement ConcentrationCalculator
**File**: `src/market/concentration.py` (create)

```python
from decimal import Decimal
from typing import List

class ConcentrationCalculator:
    """Calculate lead concentration using HHI."""
    
    def calculate(self, stocks: List[StockData]) -> Decimal:
        """
        Calculate concentration for a sector.
        
        Args:
            stocks: List of stocks in sector with market_score attribute
        
        Returns:
            Normalized HHI (0-1)
        """
        # Filter to leader candidates
        candidates = [s for s in stocks if self._is_leader_candidate(s)]
        
        if not candidates:
            return Decimal("0")
        
        strengths = [s.market_score for s in candidates]
        total = sum(strengths)
        
        if total == 0:
            return Decimal("0")
        
        # Calculate shares
        shares = [s / total for s in strengths]
        
        # HHI
        hhi = sum(s ** 2 for s in shares)
        
        # Normalize
        n = len(candidates)
        if n == 1:
            return Decimal("1")  # Single stock = max concentration
        
        min_hhi = Decimal(str(1 / n))
        normalized = (hhi - min_hhi) / (Decimal("1") - min_hhi)
        
        return normalized
    
    def _is_leader_candidate(self, stock: StockData) -> bool:
        """Determine if stock is a leader candidate."""
        # Leader candidates: top performers by market score
        return stock.market_score > Decimal("0.5")
    
    def interpret(self, concentration: Decimal) -> str:
        """Interpret concentration level."""
        if concentration > Decimal("0.6"):
            return "high"  # 龙头带动
        elif concentration > Decimal("0.3"):
            return "medium"  # Balanced
        else:
            return "low"  # 快速轮动
```

### Task 2: Add concentration to sector snapshot
**File**: `src/market/models.py` (modify SectorScore)

Add field:
```python
lead_concentration = Column(Numeric(7, 4))  # Normalized HHI (0-1)
concentration_interpretation = Column(String(20))  # high/medium/low
```

### Task 3: Integrate with SectorRadarService
**File**: `src/market/sector_radar.py` (modify)

```python
class SectorRadarService:
    def __init__(self):
        self.technical_calc = TechnicalScoreCalculator(...)
        self.sentiment_calc = SentimentScoreCalculator(...)
        self.concentration_calc = ConcentrationCalculator()  # New
    
    async def generate_snapshot(self, sector_id: str, snapshot_date: date) -> SectorScore:
        stocks = await self._get_sector_stocks(sector_id)
        
        # ... existing score calculations ...
        
        # Calculate concentration
        concentration = self.concentration_calc.calculate(stocks)
        interpretation = self.concentration_calc.interpret(concentration)
        
        score = SectorScore(
            ...
            lead_concentration=concentration,
            concentration_interpretation=interpretation,
        )
```

### Task 4: Create query interface
**File**: `src/market/concentration.py` (append)

```python
class ConcentrationQueries:
    """Query concentration data."""
    
    @staticmethod
    async def get_sector_concentration(sector_id: str) -> Optional[Decimal]:
        """Get current concentration for a sector."""
    
    @staticmethod
    async def get_high_concentration_sectors() -> List[str]:
        """Get sectors with high concentration (>0.6)."""
    
    @staticmethod
    async def get_concentration_history(sector_id: str, days: int = 30) -> List[Tuple[date, Decimal]]:
        """Get concentration history for a sector."""
```

### Task 5: Create unit tests
**File**: `tests/test_concentration.py`

Test cases:
- HHI calculation (single stock = 1.0)
- HHI calculation (equal stocks = 0.0)
- HHI calculation (mixed concentration)
- Normalization correctness
- Interpretation logic
- Empty sector handling

## Success Criteria
- [ ] ConcentrationCalculator implements HHI correctly
- [ ] Normalization works for various n values
- [ ] Interpretation logic is accurate
- [ ] SectorScore includes concentration fields
- [ ] Query methods work correctly
- [ ] Unit tests pass

## Dependencies
- MARKET-01: Sector radar (completed)

## Notes
- HHI is standard economics measure for market concentration
- High concentration = dragon leader driving sector
- Low concentration = rapid rotation, broad participation
