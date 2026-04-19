# Phase 2: Macro Environment - Research Summary

**Researched:** 2026-04-19  
**Domain:** China Macro Framework for A-Stock Quantitative Trading  
**Confidence:** HIGH (well-established frameworks in Chinese institutional research)

---

## 1. Macro Five-Dimension Scoring Framework

### Framework Overview

The five-dimension macro scoring system is widely used by Chinese institutional investors for top-down asset allocation:

| Dimension | Key Indicators | Data Source | Frequency |
|-----------|---------------|-------------|-----------|
| **流动性 (Liquidity)** | M2 YoY, 社融增量，DR007, 10Y 国债收益率 | PBOC, NIFD | Monthly |
| **增长 (Growth)** | GDP YoY, PMI, 工业增加值，固定资产投资 | NBS, Caixin | Monthly/Quarterly |
| **通胀成本 (Inflation/Cost)** | CPI YoY, PPI YoY, 原油价格 | NBS, Wind | Monthly |
| **政策 (Policy)** | 财政政策力度，货币政策取向，产业政策 | State Council, Ministries | Event-driven |
| **全球 (Global)** | 美联储利率，美元指数，中美利差，大宗商品价格 | Fed, Bloomberg | Monthly |

### Scoring Methodology

Each dimension scored -1 to +1:
- **+1**: Strong tailwind (e.g., liquidity expansion, growth acceleration)
- **0**: Neutral
- **-1**: Strong headwind (e.g., liquidity tightening, growth slowdown)

**Composite macro score** = weighted average of 5 dimensions (equal weight = 0.2 each)

### Key Data Sources for China Macro

| Source | Coverage | Access |
|--------|----------|--------|
| **PBOC (中国人民银行)** | M2, 社融，信贷数据 | Official website, monthly |
| **NBS (国家统计局)** | GDP, CPI, PPI, PMI, industrial production | Official website |
| **Wind/Choice** | Aggregated macro database | Paid subscription |
| **Akshare/Tushare** | Some macro data via API | Free/Paid tier |

---

## 2. Monetary-Credit Quadrant Framework

### The Four Quadrants

The monetary-credit framework maps liquidity (monetary) and growth (credit) conditions into four regimes:

```
                    Credit Conditions
                    Wide (Expansion)    Narrow (Contraction)
Monetary    Wide    ┌─────────────────┬─────────────────┐
Conditions  (Easy)  │ 宽货币 + 宽信用  │ 宽货币 + 紧信用  │
                    │ Growth: +0.8    │ Growth: +0.2    │
                    │ Liquidity: +0.6 │ Liquidity: +0.8 │
                    │ Policy: +0.7    │ Policy: +0.5    │
                    │ → Risk ON       │ → Defensive     │
                    │ → Cyclicals     │ → Bonds/Gold    │
                    ├─────────────────┼─────────────────┤
            Narrow  │ 紧货币 + 宽信用  │ 紧货币 + 紧信用  │
            (Tight) │ Growth: +0.3    │ Growth: -0.7    │
                    │ Liquidity: -0.5 │ Liquidity: -0.8 │
                    │ Policy: -0.3    │ Policy: -0.7    │
                    │ → Selective     │ → Risk OFF      │
                    │ → Quality       │ → Cash/Bonds    │
                    └─────────────────┴─────────────────┘
```

### Quadrant Characteristics

| Quadrant | Macro Multiplier | Risk Appetite | Sector Preference | Positioning |
|----------|------------------|---------------|-------------------|-------------|
| **宽货币 + 宽信用** | 1.10-1.15 | High | Cyclicals, Growth | Overweight |
| **宽货币 + 紧信用** | 1.00-1.05 | Moderate | Defensive, Bonds | Neutral |
| **紧货币 + 宽信用** | 0.95-1.00 | Selective | Quality, Value | Underweight |
| **紧货币 + 紧信用** | 0.85-0.90 | Low | Cash, Gold | Light position |

### Determining Quadrant

**Monetary condition** (liquidity):
- M2 YoY > 10% → Wide (+1)
- M2 YoY 8-10% → Neutral (0)
- M2 YoY < 8% → Tight (-1)

**Credit condition** (growth):
- 社融增量 YoY > 15% → Wide (+1)
- 社融增量 YoY 10-15% → Neutral (0)
- 社融增量 YoY < 10% → Tight (-1)

**Thresholds should be configurable** for backtesting optimization.

---

## 3. Implementation Considerations

### Data Availability

| Indicator | Tushare | Akshare | Efinance | PBOC Direct |
|-----------|---------|---------|----------|-------------|
| M2 YoY | ✓ (ts_money_supply) | ✓ | ✓ | ✓ |
| 社融增量 | ✓ (ts_social_financing) | ✓ | Partial | ✓ |
| GDP YoY | ✓ | ✓ | ✗ | ✓ |
| PMI | ✓ | ✓ | ✓ | ✓ |
| CPI/PPI | ✓ | ✓ | ✓ | ✓ |
| DR007 | ✓ | ✓ | ✓ | ✓ |
| 10Y 国债 | ✓ | ✓ | ✓ | ✓ |

**Recommendation:** Use Tushare as primary (if token available), Akshare as fallback for free tier.

### Update Frequency

- **Most macro data**: Monthly (released 10-15 days after month-end)
- **PMI**: Monthly (released at month-end)
- **GDP**: Quarterly (released ~15 days after quarter-end)
- **Policy events**: Event-driven (unpredictable)

**Refresh strategy:**
- Scheduled monthly refresh (e.g., 15th of each month)
- Event-triggered refresh for policy announcements
- Graceful degradation: use previous month's data if new data unavailable

### Macro Multiplier Application

The `macro_multiplier` acts as a **global risk adjustment factor**:

```python
# Example calculation
macro_multiplier = 1.0 + (composite_score * 0.15)
# Bounds: [0.85, 1.15]

# Applied to position sizing
final_position = base_position * macro_multiplier
```

**Key insight:** Macro doesn't change stock rankings, but adjusts overall exposure.

---

## 4. Competitive Intelligence

### How Institutional Investors Use This Framework

1. **Top-down allocation**: Macro regime determines overall仓位 (position level)
2. **Sector rotation**: Different quadrants favor different sectors
3. **Risk management**: Tight-tight quadrant triggers defensive posture

### Common Pitfalls

| Pitfall | Consequence | Mitigation |
|---------|-------------|------------|
| Overfitting thresholds | Backtest looks great, live trading fails | Use wide thresholds, test across regimes |
| Lagging indicator reliance | Data released 10-15 days late | Use high-frequency proxies (DR007,票据利率) |
| Policy misreading | "Prudent" can mean tight or neutral | NLP on policy statements, expert judgment |
| Global factor neglect | 2022 USD strength impacted A-shares | Include Fed policy, DXY in global dimension |

---

## 5. Recommendations for Phase 2

### MVP Scope (Must Have)

1. **Five-dimension scoring module**
   - Data fetchers for M2, 社融，CPI, PPI, PMI
   - Configurable scoring thresholds
   - Output: composite_score (-1 to +1)

2. **Monetary-credit quadrant判定**
   - M2 YoY → monetary condition
   - 社融 YoY → credit condition
   - Output: quadrant label + macro_multiplier

3. **Monthly refresh scheduler**
   - Integrate with existing APScheduler
   - Graceful degradation if data unavailable

4. **Logging and monitoring**
   - Log macro scores for each dimension
   - Alert on data fetch failures

### Deferred to Phase 3+

- Event-triggered policy updates (requires NLP on policy statements)
- High-frequency liquidity proxies (票据利率，interbank rates)
- Global dimension deep dive (Fed policy, DXY impact modeling)
- Backtesting framework for threshold optimization

---

## 6. Data Model Design

### MacroSnapshot Table

```sql
CREATE TABLE macro_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    snapshot_date DATE NOT NULL,  -- e.g., 2026-04-01
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Liquidity dimension
    m2_yoy DECIMAL(5,2),          -- M2 同比%
    dr007_avg DECIMAL(5,4),       -- DR007 月均值%
    bond_10y_yield DECIMAL(5,4),  -- 10Y 国债收益率%
    liquidity_score DECIMAL(3,2), -- -1.0 to +1.0
    
    -- Growth dimension
    gdp_yoy DECIMAL(5,2),         -- GDP 同比%
    pmi_manufacturing DECIMAL(5,2), -- 制造业 PMI
    industrial_prod_yoy DECIMAL(5,2), -- 工业增加值%
    growth_score DECIMAL(3,2),    -- -1.0 to +1.0
    
    -- Inflation dimension
    cpi_yoy DECIMAL(5,2),         -- CPI 同比%
    ppi_yoy DECIMAL(5,2),         -- PPI 同比%
    oil_price_change DECIMAL(5,2), -- 原油价格变动%
    inflation_score DECIMAL(3,2), -- -1.0 to +1.0
    
    -- Policy dimension
    fiscal_stance_score DECIMAL(3,2), -- 财政政策力度
    monetary_stance_score DECIMAL(3,2), -- 货币政策取向
    policy_score DECIMAL(3,2),    -- -1.0 to +1.0
    
    -- Global dimension
    fed_rate DECIMAL(5,4),        -- 联邦基金利率%
    dxy_index DECIMAL(6,2),       -- 美元指数
    us_cn_spread DECIMAL(5,4),    -- 中美 10Y 利差%
    global_score DECIMAL(3,2),    -- -1.0 to +1.0
    
    -- Composite
    composite_score DECIMAL(3,2), -- 五维度综合得分
    monetary_condition ENUM('wide', 'neutral', 'tight'),
    credit_condition ENUM('wide', 'neutral', 'tight'),
    quadrant ENUM('wide-wide', 'wide-tight', 'tight-wide', 'tight-tight'),
    macro_multiplier DECIMAL(4,3) -- 0.85 to 1.15
    
    UNIQUE KEY unique_snapshot (snapshot_date)
);
```

---

## Sources

- PBOC official data releases: [中国人民银行](http://www.pbc.gov.cn)
- NBS official data: [国家统计局](http://www.stats.gov.cn)
- Macro framework references: Institutional research reports (CICC, CITIC)
- Akshare macro data documentation: [akshare](https://akshare.akfamily.xyz)
- Tushare macro data API: [Tushare Pro](https://tushare.pro)

---

*Research completed: 2026-04-19*
