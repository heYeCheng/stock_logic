---
plan_id: MARKET-04
phase: 4
requirement: MARKET-04
title: Structure Markers
description: Implement sector structure classification (聚焦/扩散/快速轮动)
type: feature
estimated_effort: 1h
---

# Plan: MARKET-04 - Structure Markers

## Goal
Implement sector structure markers that classify market structure as 聚焦 (concentrated), 扩散 (diffuse), or 快速轮动 (rapid rotation).

## Context
- Research: .planning/phases/phase-4/RESEARCH.md (MARKET-04 section)
- Dependencies: MARKET-01 (sector radar), MARKET-03 (concentration)

## Classification Logic

```python
def determine_structure_marker(concentration: Decimal, breadth: Decimal, turnover: Decimal) -> str:
    """
    Determine sector structure marker.
    
    Args:
        concentration: Lead concentration (0-1) from MARKET-03
        breadth: Percentage of stocks above MA20 (0-1)
        turnover: Sector turnover rate vs historical (1.0 = average)
    
    Returns:
        "聚焦" | "扩散" | "快速轮动" | "正常"
    """
    if concentration > Decimal("0.6") and breadth < Decimal("0.4"):
        return "聚焦"  # Leadership concentrated, narrow breadth
    elif concentration < Decimal("0.4") and breadth > Decimal("0.6"):
        return "扩散"  # Broad participation
    elif turnover > Decimal("1.5"):  # 50% above average
        return "快速轮动"  # High turnover
    else:
        return "正常"
```

## Tasks

### Task 1: Implement StructureMarkerService
**File**: `src/market/structure.py` (create)

```python
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class StructureMarker:
    """Sector structure marker."""
    sector_id: str
    snapshot_date: date
    marker: str  # 聚焦/扩散/快速轮动/正常
    concentration: Decimal
    breadth: Decimal
    turnover: Decimal
    confidence: float

class StructureMarkerService:
    """Determine sector structure markers."""
    
    def __init__(self):
        pass
    
    def determine_marker(
        self,
        concentration: Decimal,
        breadth: Decimal,
        turnover: Decimal
    ) -> str:
        """Determine structure marker."""
        if concentration > Decimal("0.6") and breadth < Decimal("0.4"):
            return "聚焦"
        elif concentration < Decimal("0.4") and breadth > Decimal("0.6"):
            return "扩散"
        elif turnover > Decimal("1.5"):
            return "快速轮动"
        else:
            return "正常"
    
    def calculate_confidence(
        self,
        concentration: Decimal,
        breadth: Decimal,
        turnover: Decimal,
        marker: str
    ) -> float:
        """Calculate confidence in marker assignment."""
        if marker == "聚焦":
            # How far into the region
            conc_dist = float(concentration - Decimal("0.6"))
            breadth_dist = float(Decimal("0.4") - breadth)
            return min(conc_dist, breadth_dist)
        elif marker == "扩散":
            conc_dist = float(Decimal("0.4") - concentration)
            breadth_dist = float(breadth - Decimal("0.6"))
            return min(conc_dist, breadth_dist)
        elif marker == "快速轮动":
            return float(turnover - Decimal("1.5")) / Decimal("1.5")
        else:
            # Normal - distance from any boundary
            return 1.0  # Default high confidence for normal
    
    async def generate_marker(
        self,
        sector_id: str,
        snapshot_date: date,
        stocks: List[StockData]
    ) -> StructureMarker:
        """Generate structure marker for a sector."""
        
        # Get inputs
        concentration = await self._get_concentration(sector_id, snapshot_date)
        breadth = self._calculate_breadth(stocks)
        turnover = await self._get_turnover(sector_id, snapshot_date)
        
        # Determine marker
        marker = self.determine_marker(concentration, breadth, turnover)
        
        # Calculate confidence
        confidence = self.calculate_confidence(concentration, breadth, turnover, marker)
        
        return StructureMarker(
            sector_id=sector_id,
            snapshot_date=snapshot_date,
            marker=marker,
            concentration=concentration,
            breadth=breadth,
            turnover=turnover,
            confidence=confidence
        )
```

### Task 2: Add structure marker to sector snapshot
**File**: `src/market/models.py` (modify SectorScore)

Add fields:
```python
structure_marker = Column(String(20))  # 聚焦/扩散/快速轮动/正常
structure_confidence = Column(Float)
```

### Task 3: Integrate with SectorRadarService
**File**: `src/market/sector_radar.py` (modify)

```python
class SectorRadarService:
    def __init__(self):
        # ... existing ...
        self.structure_service = StructureMarkerService()
    
    async def generate_snapshot(self, sector_id: str, snapshot_date: date) -> SectorScore:
        stocks = await self._get_sector_stocks(sector_id)
        
        # ... existing score calculations ...
        
        # Generate structure marker
        marker = await self.structure_service.generate_marker(
            sector_id, snapshot_date, stocks
        )
        
        score = SectorScore(
            ...
            structure_marker=marker.marker,
            structure_confidence=marker.confidence,
        )
```

### Task 4: Create query interface
**File**: `src/market/structure.py` (append)

```python
class StructureQueries:
    """Query structure markers."""
    
    @staticmethod
    async def get_current_markers() -> Dict[str, str]:
        """Get current structure markers for all sectors."""
    
    @staticmethod
    async def get_sectors_by_marker(marker: str) -> List[str]:
        """Get sectors with a specific marker."""
    
    @staticmethod
    async def get_marker_history(sector_id: str, days: int = 30) -> List[Tuple[date, str]]:
        """Get structure marker history for a sector."""
```

### Task 5: Create unit tests
**File**: `tests/test_structure.py`

Test cases:
- Marker determination (聚焦 condition)
- Marker determination (扩散 condition)
- Marker determination (快速轮动 condition)
- Marker determination (normal/default)
- Confidence calculation
- Breadth calculation
- Turnover calculation

## Success Criteria
- [ ] StructureMarkerService determines markers correctly
- [ ] Confidence calculation works
- [ ] SectorScore includes structure fields
- [ ] Query methods return correct data
- [ ] Unit tests pass

## Dependencies
- MARKET-01: Sector radar (completed)
- MARKET-03: Concentration (completed)

## Notes
- Structure markers help identify market regime
- 聚焦 = dragon leader driving, narrow breadth
- 扩散 = broad participation, healthy advance
- 快速轮动 = hot money rotating quickly
