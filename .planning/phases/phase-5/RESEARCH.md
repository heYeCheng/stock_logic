# Phase 5 Research: Execution Layer

**Phase**: 5  
**Name**: Execution Layer  
**Goal**: Continuous position function and A-share trading constraint enforcement  
**Research Date**: 2026-04-19

---

## Overview

Phase 5 implements the **execution layer** that converts stock scores into actionable position recommendations while enforcing A-share trading constraints. This is the final layer before the Web UI presentation layer.

### Architecture

```
Phase 5 Execution Layer
├── EXEC-01: Continuous position function
├── EXEC-02: A-share trading constraints
├── EXEC-03: Stock recommendation markers
└── EXEC-04: Stop-loss and hold decisions
```

### Key Design Principles

1. **Continuous function**: Replace discrete matrix with smooth position scaling
2. **Constraint-first**: A-share rules enforced before recommendations
3. **Explainable markers**: Clear categorization of recommendation rationale
4. **Risk management**: Stop-loss and hold rules protect capital

---

## EXEC-01: Continuous Position Function

### Purpose

Convert composite scores into continuous position recommendations (0-100%).

### Input Signals

| Signal | Source | Weight |
|--------|--------|--------|
| `composite_score` | Phase 4 (STOCK-08) | 50% |
| `macro_multiplier` | Phase 2 (MACRO-02) | 30% |
| `sector_state` | Phase 4 (MARKET-02) | 20% |

### Position Function

```python
def calculate_position(
    composite_score: Decimal,      # 0-1 from STOCK-08
    macro_multiplier: Decimal,      # 0.5-1.5 from MACRO-02
    sector_state: SectorState,      # weak/normal/overheated
) -> Decimal:
    """
    Continuous position recommendation.
    
    Returns:
        Position percentage (0.0 - 1.0)
    """
    # Base position from composite score (sigmoid scaling)
    base_position = sigmoid(composite_score * 2 - 1)  # Maps 0-1 to ~0-1
    
    # Macro overlay
    macro_adjusted = base_position * macro_multiplier
    
    # Sector state overlay
    state_multiplier = {
        SectorState.weak: Decimal("0.5"),      # Reduce in weak sectors
        SectorState.normal: Decimal("1.0"),    # Full position
        SectorState.overheated: Decimal("0.7"), # Reduce in overheated
    }[sector_state]
    
    final_position = macro_adjusted * state_multiplier
    
    # Clamp to 0-1
    return max(Decimal("0"), min(Decimal("1"), final_position))
```

### Position Tiers

For practical trading, continuous positions map to tiers:

| Tier | Range | Meaning |
|------|-------|---------|
| 空仓 | 0-10% | No position |
| 轻仓 | 10-30% | Light position |
| 中等 | 30-60% | Moderate position |
| 重仓 | 60-80% | Heavy position |
| 满仓 | 80-100% | Full position |

### Output Schema

```python
{
    "stock_code": "000001.SZ",
    "snapshot_date": date,
    "composite_score": Decimal("0.72"),
    "macro_multiplier": Decimal("1.1"),
    "sector_state": "normal",
    "recommended_position": Decimal("0.65"),  # 65%
    "position_tier": "重仓",
}
```

---

## EXEC-02: A-Share Trading Constraints

### Purpose

Enforce A-share specific trading rules that may override position recommendations.

### Constraints

#### 1. Limit Up/Down Check

```python
def check_limit_status(stock_code: str, current_price: Decimal, prev_close: Decimal) -> str:
    """
    Check if stock is at limit up or limit down.
    
    Returns:
        "limit_up" | "limit_down" | "normal"
    """
    change_pct = (current_price - prev_close) / prev_close
    
    # ST stocks: ±5%, others: ±10%, STAR Market: ±20%
    limit_threshold = get_limit_threshold(stock_code)
    
    if change_pct >= limit_threshold - 0.001:  # Small tolerance
        return "limit_up"
    elif change_pct <= -limit_threshold + 0.001:
        return "limit_down"
    else:
        return "normal"
```

**Constraint Logic**:
- `limit_up`: Cannot buy (already locked at limit)
- `limit_down`: Cannot sell (already locked at limit)

#### 2. Suspension Check

```python
def check_suspension(stock_code: str) -> bool:
    """
    Check if stock is suspended from trading.
    
    Returns:
        True if suspended, False otherwise
    """
    # Query Tushare suspend_status API
    return is_suspended
```

**Constraint Logic**:
- `suspended`: Cannot buy or sell

#### 3. Chasing Risk Check (追高风险)

```python
def check_chasing_risk(
    current_price: Decimal,
    ma20: Decimal,
    ma60: Decimal,
    consecutive_gains: int
) -> str:
    """
    Assess chasing risk.
    
    Returns:
        "high" | "medium" | "low"
    """
    # High risk: price > 30% above MA20, or 5+ consecutive gains
    if current_price > ma20 * Decimal("1.3") or consecutive_gains >= 5:
        return "high"
    elif current_price > ma20 * Decimal("1.15") or consecutive_gains >= 3:
        return "medium"
    else:
        return "low"
```

**Constraint Logic**:
- `high`: Recommend reducing position by 50%
- `medium`: No constraint, but flag in recommendation
- `low`: No constraint

### Constraint Enforcement Order

```python
def enforce_constraints(
    recommended_position: Decimal,
    limit_status: str,
    is_suspended: bool,
    chasing_risk: str
) -> Tuple[Decimal, List[str]]:
    """
    Apply constraints in order.
    
    Returns:
        (final_position, list of applied constraints)
    """
    constraints = []
    position = recommended_position
    
    # 1. Suspension (hard block)
    if is_suspended:
        return Decimal("0"), ["suspended"]
    
    # 2. Limit up (cannot buy)
    if limit_status == "limit_up":
        return Decimal("0"), ["limit_up_cannot_buy"]
    
    # 3. Limit down (cannot sell, but can hold)
    if limit_status == "limit_down":
        if position > 0:
            position = Decimal("0")  # Cannot add to falling knife
            constraints.append("limit_down_cannot_add")
    
    # 4. Chasing risk (reduce exposure)
    if chasing_risk == "high":
        position = position * Decimal("0.5")
        constraints.append("chasing_risk_high")
    
    return position, constraints
```

---

## EXEC-03: Stock Recommendation Markers

### Purpose

Categorize recommendation rationale for user understanding.

### Marker Types

| Marker | Meaning | Criteria |
|--------|---------|----------|
| 逻辑受益股 | Logic beneficiary | High logic score, direct event exposure |
| 关联受益股 | Related beneficiary | Medium logic score, indirect exposure |
| 情绪跟风股 | Sentiment follower | High market score, low logic score |

### Classification Logic

```python
def determine_recommendation_marker(
    logic_score: Decimal,
    market_score: Decimal,
    exposure_coefficient: Decimal,
    catalyst_level: str
) -> str:
    """
    Determine recommendation marker.
    
    Returns:
        "逻辑受益股" | "关联受益股" | "情绪跟风股"
    """
    # Logic beneficiary: high logic score + high exposure
    if logic_score >= Decimal("0.7") and exposure_coefficient >= Decimal("0.5"):
        return "逻辑受益股"
    
    # Related beneficiary: medium logic score
    elif logic_score >= Decimal("0.4") and exposure_coefficient >= Decimal("0.3"):
        return "关联受益股"
    
    # Sentiment follower: high market score, low logic
    elif market_score >= Decimal("0.6") and logic_score < Decimal("0.4"):
        return "情绪跟风股"
    
    # Default: logic beneficiary if composite is high
    else:
        return "逻辑受益股"
```

### Output Schema

```python
{
    "stock_code": "000001.SZ",
    "snapshot_date": date,
    "marker": "逻辑受益股",
    "marker_reason": "High logic score (0.75) with strong exposure (0.62)",
}
```

---

## EXEC-04: Stop-Loss and Hold Decisions

### Purpose

Apply consistent rules for stop-loss and hold decisions.

### Stop-Loss Rules

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Logic score < 0.3 | Sell | Core logic invalidated |
| Price < entry × 0.92 | Sell | 8% hard stop-loss |
| Sector state = weak | Reduce 50% | Sector-wide weakness |
| Catalyst expired | Sell | Event-driven thesis complete |

### Hold Rules

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Logic score ≥ 0.7 | Hold | Strong logic intact |
| Market score ≥ 0.7 | Hold | Market momentum positive |
| Composite ≥ 0.6 | Hold | Overall score supportive |

### Decision Function

```python
def make_hold_decision(
    current_position: Decimal,
    logic_score: Decimal,
    market_score: Decimal,
    composite_score: Decimal,
    entry_price: Decimal,
    current_price: Decimal,
    sector_state: SectorState,
    catalyst_active: bool
) -> Tuple[str, Decimal]:
    """
    Make hold/sell/reduce decision.
    
    Returns:
        (action, new_position)
        action: "hold" | "sell" | "reduce"
    """
    # Stop-loss triggers
    if logic_score < Decimal("0.3"):
        return "sell", Decimal("0")
    
    if current_price < entry_price * Decimal("0.92"):
        return "sell", Decimal("0")
    
    if not catalyst_active and logic_score < Decimal("0.5"):
        return "sell", Decimal("0")
    
    # Reduce triggers
    if sector_state == SectorState.weak:
        return "reduce", current_position * Decimal("0.5")
    
    # Hold triggers
    if composite_score >= Decimal("0.6"):
        return "hold", current_position
    
    if logic_score >= Decimal("0.7") or market_score >= Decimal("0.7"):
        return "hold", current_position
    
    # Default: hold if no strong signal
    return "hold", current_position
```

### Output Schema

```python
{
    "stock_code": "000001.SZ",
    "snapshot_date": date,
    "current_position": Decimal("0.5"),
    "action": "hold",
    "recommended_position": Decimal("0.5"),
    "action_reason": "Composite score (0.65) supports holding",
}
```

---

## Integration with Phase 6 (Web UI)

Phase 5 outputs feed directly into Phase 6 Web UI:

| Phase 5 Output | Phase 6 Display |
|----------------|-----------------|
| Position recommendation | Stock card percentage |
| Recommendation marker | Badge/tag on stock card |
| Constraint flags | Warning icons |
| Hold/sell decision | Action button suggestions |

---

## Dependencies

| Dependency | Source Phase | Usage |
|------------|--------------|-------|
| `composite_score` | Phase 4 (STOCK-08) | Position calculation |
| `macro_multiplier` | Phase 2 (MACRO-02) | Position overlay |
| `sector_state` | Phase 4 (MARKET-02) | Position overlay |
| `logic_score` | Phase 4 (STOCK-04) | Marker classification |
| `market_score` | Phase 4 (STOCK-05) | Marker classification |
| `exposure_coefficient` | Phase 4 (STOCK-02) | Marker classification |
| `catalyst_level` | Phase 4 (STOCK-06) | Stop-loss trigger |
| `dragon_status` | Phase 4 (STOCK-07) | Sentiment factor |

---

## Testing Strategy

### Unit Tests

- Position function (sigmoid scaling, macro overlay, state overlay)
- Constraint enforcement (limit up/down, suspension, chasing risk)
- Marker classification (boundary conditions)
- Hold/sell decision (all rule combinations)

### Integration Tests

- End-to-end: composite score → position → constraints → final recommendation
- Constraint interactions (multiple constraints applied together)
- Hold decision with conflicting signals

### Test Data

Use Phase 4 outputs as test inputs:
- Composite scores from STOCK-08
- Sector states from MARKET-02
- Logic/market scores from STOCK-04/05

---

## Implementation Notes

1. **Continuous vs discrete**: Sigmoid function provides smooth transitions
2. **Constraint priority**: Hard constraints (suspension) override soft (chasing risk)
3. **Marker explainability**: Always provide reason string for user understanding
4. **Hold decision conservatism**: Default to hold when signals conflict

---

*Last updated: 2026-04-19*
