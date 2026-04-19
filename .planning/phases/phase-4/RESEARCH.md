# Phase 4 Research: Market Layer

**Phase**: 4  
**Name**: Market Layer  
**Goal**: Pure volume-price market analysis for sectors and individual stocks  
**Research Date**: 2026-04-19

---

## Overview

Phase 4 implements the **market layer** that analyzes pure volume-price data, completely separate from the logic layer. This separation ensures that market sentiment and technical analysis remain independent from fundamental logic scoring.

### Architecture

```
L2 Sector Market Layer (纯量价分析)
├── MARKET-01: Sector radar (technical + sentiment scores)
├── MARKET-02: Three-state determination (weak/normal/overheated)
├── MARKET-03: Lead concentration calculation
├── MARKET-04: Structure markers (聚焦/扩散/快速轮动)
└── MARKET-05: Tushare limit board data ingestion

L3 Stock Layer (个股承接)
├── STOCK-01: Stock-sector mapping table
├── STOCK-02: Exposure coefficient calculation
├── STOCK-03: Keyword library auto-generation
├── STOCK-04: Stock logic score
├── STOCK-05: Stock market radar
├── STOCK-06: Catalyst markers
├── STOCK-07: Dragon/zhongjun/follower identification
└── STOCK-08: Composite score (50% logic + 50% market)
```

### Key Design Principles

1. **Strict separation**: Market layer uses ONLY volume-price data, never logic scores
2. **Three-state machine**: Simplified from five states (weak/normal/overheated)
3. **Lead-lag analysis**: Identifies sector leaders and followers
4. **Exposure mapping**: Stock-sector affiliation determines logic exposure

---

## MARKET-01: Sector Market Radar

### Purpose
Generate technical and sentiment scores for each sector based purely on volume-price data.

### Technical Score Components
- **Trend strength**: 20-day vs 60-day MA slope
- **Momentum**: RSI, MACD histogram
- **Volume**: 5-day avg volume vs 20-day avg
- **Volatility**: ATR normalized

### Sentiment Score Components
- **Limit board frequency**: Count of limit-up stocks in sector
- **Dragon leader presence**: Whether sector has a recognized leader
- **Continuity**: Consecutive days with positive performance
- **Breadth**: Percentage of stocks above 20-day MA

### Output Schema
```python
{
    "sector_id": "sector_5g",
    "sector_name": "5G 概念",
    "snapshot_date": date,
    "technical_score": Decimal("0.72"),  # 0-1 scale
    "sentiment_score": Decimal("0.65"),  # 0-1 scale
    "composite_score": Decimal("0.685"),  # (technical + sentiment) / 2
}
```

---

## MARKET-02: Three-State Determination

### Purpose
Classify each sector into one of three states: weak, normal, or overheated.

### State Thresholds
```python
class SectorState(Enum):
    weak = "weak"           # composite_score < 0.35
    normal = "normal"       # 0.35 <= composite_score <= 0.70
    overheated = "overheated"  # composite_score > 0.70
```

### Hysteresis Logic
To prevent rapid state flipping:
- weak → normal: requires composite_score > 0.40
- normal → overheated: requires composite_score > 0.75
- overheated → normal: requires composite_score < 0.65
- normal → weak: requires composite_score < 0.30

### Output
```python
{
    "sector_id": "sector_5g",
    "state": "normal",
    "state_confidence": 0.85,  # How far from boundaries
    "consecutive_days": 3,     # Days in current state
}
```

---

## MARKET-03: Lead Concentration

### Purpose
Calculate how concentrated leadership is within a sector (替代分支分析).

### Algorithm
```python
def calculate_lead_concentration(stocks_in_sector):
    """
    Measures if leadership is concentrated in few stocks or diffuse.
    
    Uses Herfindahl-Hirschman Index (HHI) on strength scores.
    """
    strengths = [s.market_score for s in stocks_in_sector if s.is_leader_candidate]
    
    if not strengths:
        return 0.0
    
    total = sum(strengths)
    if total == 0:
        return 0.0
    
    # Calculate market shares
    shares = [s / total for s in strengths]
    
    # HHI: sum of squared market shares
    hhi = sum(s ** 2 for s in shares)
    
    # Normalize to 0-1 (HHI ranges from 1/n to 1)
    n = len(strengths)
    min_hhi = 1 / n
    normalized_hhi = (hhi - min_hhi) / (1 - min_hhi)
    
    return normalized_hhi
```

### Interpretation
- **High concentration (>0.6)**: Leadership concentrated in few stocks (龙头带动)
- **Medium (0.3-0.6)**: Balanced leadership
- **Low (<0.3)**: Diffuse leadership, sector rotation (快速轮动)

---

## MARKET-04: Structure Markers

### Purpose
Output sector structure markers: 聚焦/扩散/快速轮动

### Classification Logic
```python
def determine_structure_marker(concentration, breadth, turnover):
    """
    concentration: lead concentration (0-1)
    breadth: percentage of stocks above MA20
    turnover: sector turnover rate vs historical
    """
    
    if concentration > 0.6 and breadth < 0.4:
        return "聚焦"  # Leadership concentrated, narrow breadth
    elif concentration < 0.4 and breadth > 0.6:
        return "扩散"  # Broad participation
    elif turnover > 1.5:  # 50% above average
        return "快速轮动"  # High turnover
    else:
        return "正常"
```

---

## MARKET-05: Tushare Limit Board Data

### Purpose
Ingest Tushare limit-up/limit-down data for sentiment analysis.

### Data Tables
```sql
-- Daily limit board data
CREATE TABLE tushare_limit_list (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    exchange VARCHAR(10),
    name VARCHAR(50),
    type ENUM('limit_up', 'limit_down', 'st_limit_up', 'st_limit_down'),
    limit_amount DECIMAL(15, 2),
    close_price DECIMAL(15, 2),
    open_count INT,  -- Times opened
    first_time TIME,  -- First limit time
    last_time TIME,   -- Last limit time
    strong_close ENUM('strong', 'normal', 'weak'),
    index idx_date (trade_date),
    index idx_code (ts_code)
);

-- Top institutional holdings on limit days
CREATE TABLE tushare_top_inst (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    name VARCHAR(50),
    side ENUM('buy', 'sell'),
    broker VARCHAR(100),
    amount DECIMAL(15, 2),
    net_amount DECIMAL(15, 2),
    rank INT,
    index idx_date_code (trade_date, ts_code)
);
```

### API Endpoints
- `limit_list`: Daily limit board stocks
- `top_inst`: Top 5 institutional buyers/sellers

---

## STOCK-01: Stock-Sector Mapping Table

### Purpose
Maintain stock-sector affiliations (industry + concept).

### Data Model
```python
class StockSectorMapping(Base):
    __tablename__ = "stock_sector_mappings"
    
    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    sector_id = Column(String(50), nullable=False, index=True)
    sector_type = Column(String(20))  # "industry" or "concept"
    sector_name = Column(String(100))
    affiliation_strength = Column(Numeric(3, 2), default=1.0)  # 0.5-1.0
    is_primary = Column(Boolean, default=False)  # Primary sector
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

### Affiliation Strength
- **1.0**: Core/primary sector (龙头股)
- **0.7-0.9**: Strong affiliation
- **0.5-0.6**: Weak affiliation (跟风股)

---

## STOCK-02: Exposure Coefficient

### Purpose
Compute exposure coefficient: `affiliation_strength × logic_match_score`

### Formula
```python
def compute_exposure(stock, logic):
    """
    stock: StockModel with sector affiliations
    logic: LogicModel with logic_family and keywords
    """
    
    # Get max affiliation strength across matching sectors
    max_affiliation = max(
        (mapping.affiliation_strength for mapping in stock.sector_mappings),
        default=0.0
    )
    
    # Compute logic match score (keyword overlap)
    logic_keywords = set(logic.keywords)
    stock_keywords = set(stock.keywords or [])
    
    if not logic_keywords:
        logic_match_score = 0.0
    else:
        overlap = len(logic_keywords & stock_keywords)
        logic_match_score = overlap / len(logic_keywords)
    
    exposure = max_affiliation * logic_match_score
    
    return min(exposure, 1.0)  # Cap at 1.0
```

---

## STOCK-03: Keyword Auto-Generation

### Purpose
LLM generates 5-8 keywords for new sectors automatically.

### Implementation
```python
async def generate_sector_keywords(sector_name: str, sector_stocks: List[str]) -> List[str]:
    """
    Use LLM to generate 5-8 keywords for a sector.
    
    Args:
        sector_name: e.g., "5G 概念"
        sector_stocks: List of stock names in sector
    
    Returns:
        List of 5-8 keywords
    """
    prompt = f"""
    为板块"{sector_name}"生成 5-8 个关键词。
    
    板块成分股：{', '.join(sector_stocks[:10])}
    
    关键词应该：
    1. 能准确描述板块特征
    2. 用于匹配相关新闻和逻辑
    3. 避免过于宽泛（如"科技"）或过于狭窄
    
    输出 JSON 格式：
    {{
        "keywords": ["关键词 1", "关键词 2", ...]
    }}
    """
    
    response = await llm_client.generate(prompt)
    return parse_keywords(response)
```

---

## STOCK-04: Stock Logic Score

### Purpose
Calculate individual stock logic score (stock_logic_score).

### Formula
```python
def calculate_stock_logic_score(stock, logic_scores, exposure_map):
    """
    stock: StockModel
    logic_scores: Dict[logic_id, LogicScore]
    exposure_map: Dict[logic_id, exposure_coefficient]
    
    Returns:
        stock_logic_score (0-1)
    """
    
    total_weighted_score = Decimal("0")
    total_exposure = Decimal("0")
    
    for logic_id, score in logic_scores.items():
        exposure = exposure_map.get(logic_id, Decimal("0"))
        
        if exposure > 0:
            # Weight by exposure
            total_weighted_score += score.decayed_score * exposure
            total_exposure += exposure
    
    if total_exposure == 0:
        return Decimal("0")
    
    # Normalize by total exposure
    stock_logic_score = total_weighted_score / total_exposure
    
    return min(stock_logic_score, Decimal("1.0"))
```

---

## STOCK-05: Stock Market Radar

### Purpose
Individual stock market radar (technical + sentiment).

### Technical Indicators
- **MA alignment**: Price vs MA5/MA10/MA20
- **Volume trend**: 5-day avg vs 20-day avg
- **RSI**: 14-day RSI
- **MACD**: Signal line crossover

### Sentiment Indicators
- **Recent limit-ups**: Count in past 5 days
- **Dragon leader status**: Is this stock a leader?
- **Institutional buying**: Net institutional flow

### Output
```python
{
    "stock_code": "000001.SZ",
    "snapshot_date": date,
    "technical_score": Decimal("0.65"),
    "sentiment_score": Decimal("0.70"),
    "market_composite": Decimal("0.675"),
}
```

---

## STOCK-06: Catalyst Markers

### Purpose
Simplified catalyst markers: strong/medium/none

### Classification
```python
def determine_catalyst(stock, recent_events):
    """
    stock: StockModel
    recent_events: List of recent logic events affecting this stock
    """
    
    if not recent_events:
        return "none"
    
    # Count high-importance events
    high_importance_count = sum(
        1 for e in recent_events if e.importance_level == "high"
    )
    
    if high_importance_count >= 2:
        return "strong"
    elif high_importance_count == 1:
        return "medium"
    else:
        return "none"
```

---

## STOCK-07: Dragon/Leader Identification

### Purpose
Identify dragon leader (龙头), zhongjun (中军), and follower (跟风) stocks.

### Classification Criteria
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

---

## STOCK-08: Composite Score

### Purpose
Compute individual stock composite score (50% logic + 50% market).

### Formula
```python
def compute_composite_score(stock_logic_score, stock_market_score):
    """
    50% logic + 50% market
    """
    return (stock_logic_score + stock_market_score) / 2
```

### Output
```python
{
    "stock_code": "000001.SZ",
    "snapshot_date": date,
    "logic_score": Decimal("0.72"),
    "market_score": Decimal("0.65"),
    "composite_score": Decimal("0.685"),
    "recommendation_rank": 15,  # Ranked among all stocks
}
```

---

## Implementation Notes

### Data Dependencies
- **Tushare**: Daily quotes, limit board data, sector constituents
- **AKShare**: Alternative data source for fallback
- **LLM**: Keyword generation, catalyst analysis

### Performance Considerations
- **Batch processing**: Process all stocks in single query where possible
- **Caching**: Cache sector calculations (shared across stocks)
- **Incremental updates**: Only recalculate changed sectors

### Testing Strategy
- **Unit tests**: Individual scoring functions
- **Integration tests**: End-to-end snapshot generation
- **Backtest validation**: Compare signals vs historical performance

---

## Related Patterns

### Sector Rotation Detection
```python
def detect_sector_rotation(sector_scores_history):
    """
    Detect if market is rotating between sectors.
    
    High rotation = rapid changes in sector leadership
    """
    if len(sector_scores_history) < 5:
        return False
    
    # Calculate rank correlation between consecutive days
    correlations = []
    for i in range(1, len(sector_scores_history)):
        prev_ranks = rank_sectors(sector_scores_history[i-1])
        curr_ranks = rank_sectors(sector_scores_history[i])
        corr = spearman_correlation(prev_ranks, curr_ranks)
        correlations.append(corr)
    
    avg_correlation = sum(correlations) / len(correlations)
    
    # Low correlation = high rotation
    return avg_correlation < 0.5
```

### Contagion Analysis
```python
def analyze_logic_contagion(logic_family, sector_mappings):
    """
    Analyze how a logic family spreads across sectors.
    
    Returns sectors most exposed to this logic family.
    """
    sector_exposure = defaultdict(Decimal)
    
    for logic in logics:
        if logic.logic_family == logic_family:
            for mapping in sector_mappings:
                if matches_logic(mapping, logic):
                    sector_exposure[mapping.sector_id] += logic.strength
    
    return sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True)
```

---

*Research completed: 2026-04-19*
