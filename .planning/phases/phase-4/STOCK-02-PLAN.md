---
plan_id: STOCK-02
phase: 4
requirement: STOCK-02
title: Exposure Coefficient Calculation
description: Implement affiliation_strength × logic_match_score calculation
type: feature
estimated_effort: 1h
---

# Plan: STOCK-02 - Exposure Coefficient Calculation

## Goal
Implement exposure coefficient calculation: `affiliation_strength × logic_match_score`

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (STOCK-02 section)
- Models: src/market/models.py, src/logic/models.py
- Dependencies: STOCK-01 (sector mappings), Phase 3 (logic models)

## Formula

```python
def compute_exposure(stock, logic):
    """
    stock: StockModel with sector affiliations
    logic: LogicModel with logic_family and keywords
    """
    
    # Get max affiliation strength across matching sectors
    max_affiliation = max(
        (mapping.affiliation_strength for mapping in stock.sector_mappings),
        default=Decimal("0")
    )
    
    # Compute logic match score (keyword overlap)
    logic_keywords = set(logic.keywords)
    stock_keywords = set(stock.keywords or [])
    
    if not logic_keywords:
        logic_match_score = Decimal("0")
    else:
        overlap = len(logic_keywords & stock_keywords)
        logic_match_score = Decimal(str(overlap / len(logic_keywords)))
    
    exposure = max_affiliation * logic_match_score
    
    return min(exposure, Decimal("1.0"))  # Cap at 1.0
```

## Tasks

### Task 1: Create ExposureCalculator
**File**: `src/market/exposure.py` (create)

```python
from decimal import Decimal
from typing import List, Dict, Optional, Set

class ExposureCalculator:
    """Calculate stock exposure to logics."""
    
    def calculate_exposure(
        self,
        stock_keywords: Set[str],
        sector_affiliations: List[StockSectorMapping],
        logic_keywords: Set[str]
    ) -> Decimal:
        """
        Calculate exposure coefficient.
        
        Args:
            stock_keywords: Keywords associated with stock
            sector_affiliations: Stock's sector mappings
            logic_keywords: Keywords from logic
        
        Returns:
            Exposure coefficient (0-1)
        """
        # Get max affiliation strength
        if not sector_affiliations:
            max_affiliation = Decimal("0")
        else:
            max_affiliation = max(
                m.affiliation_strength for m in sector_affiliations
            )
        
        # Calculate logic match score
        if not logic_keywords or not stock_keywords:
            logic_match_score = Decimal("0")
        else:
            overlap = len(logic_keywords & stock_keywords)
            logic_match_score = Decimal(str(overlap / len(logic_keywords)))
        
        # Compute exposure
        exposure = max_affiliation * logic_match_score
        
        return min(exposure, Decimal("1.0"))
    
    def calculate_batch_exposure(
        self,
        stock_keywords_map: Dict[str, Set[str]],
        sector_mappings_map: Dict[str, List[StockSectorMapping]],
        logics: List[LogicModel]
    ) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate exposure for all stock-logic pairs.
        
        Returns:
            Dict[stock_code, Dict[logic_id, exposure]]
        """
        result = {}
        
        for stock_code, keywords in stock_keywords_map.items():
            result[stock_code] = {}
            affiliations = sector_mappings_map.get(stock_code, [])
            
            for logic in logics:
                exposure = self.calculate_exposure(
                    keywords,
                    affiliations,
                    set(logic.keywords or [])
                )
                result[stock_code][logic.logic_id] = exposure
        
        return result
```

### Task 2: Create Stock model with keywords
**File**: `src/market/models.py` (append)

```python
class StockModel(Base):
    """Stock basic information."""
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True)
    ts_code = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(50))
    exchange = Column(String(10))
    industry = Column(String(50))
    keywords = Column(JSON)  # List of keywords
    market_cap = Column(Numeric(15, 2))
    list_date = Column(Date)
```

### Task 3: Create query interface
**File**: `src/market/exposure.py` (append)

```python
class ExposureQueries:
    """Query exposure data."""
    
    @staticmethod
    async def get_stock_exposures(
        stock_code: str,
        snapshot_date: date
    ) -> Dict[str, Decimal]:
        """Get all logic exposures for a stock."""
        # Query exposure_snapshots table
        pass
    
    @staticmethod
    async def get_logic_exposed_stocks(
        logic_id: str,
        min_exposure: Decimal = Decimal("0.3")
    ) -> List[str]:
        """Get stocks with significant exposure to a logic."""
        pass
    
    @staticmethod
    async def get_max_exposure_stock(
        logic_id: str
    ) -> Optional[str]:
        """Get stock with highest exposure to a logic."""
        pass
```

### Task 4: Create exposure snapshot table
**File**: `src/market/models.py` (append)

```python
class StockLogicExposure(Base):
    """Daily stock-logic exposure snapshot."""
    __tablename__ = "stock_logic_exposures"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    logic_id = Column(String(64), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    exposure_coefficient = Column(Numeric(7, 4))  # 0-1
    affiliation_strength = Column(Numeric(3, 2))
    logic_match_score = Column(Numeric(7, 4))
    
    __table_args__ = (
        UniqueConstraint('stock_code', 'logic_id', 'snapshot_date'),
    )
```

### Task 5: Create unit tests
**File**: `tests/test_exposure.py`

Test cases:
- Exposure calculation (full match)
- Exposure calculation (partial match)
- Exposure calculation (no match)
- Batch calculation
- Affiliation strength weighting
- Keyword overlap edge cases

## Success Criteria
- [ ] ExposureCalculator implements formula correctly
- [ ] StockLogicExposure model created
- [ ] Query methods work
- [ ] Migration runs
- [ ] Unit tests pass

## Dependencies
- STOCK-01: Sector mappings (completed)
- Phase 3: Logic models (completed)

## Notes
- Exposure used for stock logic scoring
- Keyword matching is simple overlap (can improve with TF-IDF later)
- Cached daily for performance
