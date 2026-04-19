# Feature Research

**Domain:** A 股量化选股系统 (Quantitative Stock Selection for A-Share Market)
**Researched:** 2026-04-19
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **每日推荐列表** | 选股系统的核心输出，用户每日查看的基准 | MEDIUM | MVP: Top 20 推荐，含综合评分、仓位建议 |
| **个股综合评分** | 用户需要直观的排序依据 | MEDIUM | 逻辑分 + 市场分加权，0-100 分展示 |
| **板块热度排行** | 用户需要知道资金流向哪里 | MEDIUM | 技术面 + 情绪面综合评分排序 |
| **技术指标展示** | A 股交易者基础需求（均线、量比、换手） | LOW | MA20/MA60、量比、相对强度 |
| **涨停板标记** | A 股特色，涨停=强情绪信号 | LOW | 近 5 日涨停次数、连板高度 |
| **龙虎榜数据** | 主力动向是 A 股核心参考 | MEDIUM | 机构净买入/净卖出标记 |
| **概念板块归属** | A 股炒作核心是概念，非行业 | MEDIUM | 支持多板块归属，显示主营概念 |
| **基础过滤条件** | 排除 ST、停牌、涨跌停不可交易状态 | LOW | 交易约束检查 |
| **仓位建议** | 用户需要明确的操作指导 | MEDIUM | 重仓/半仓/轻仓/观察四档 |
| **止损参考** | 波段交易必备风控 | LOW | 收盘价跌破 X 日线触发 |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **事件计分板驱动** | 逻辑强度可解释、可回测，非黑箱 | HIGH | 核心价值——规则引擎计算逻辑强度，非 LLM 主观打分 |
| **多逻辑并发识别** | 板块受多条逻辑共同作用，计算净推力 | HIGH | 同时追踪正向/反向逻辑，输出有无反向标记 |
| **逻辑受益度量化** | 明确个股与逻辑的关联强度，非简单概念匹配 | HIGH | 暴露系数 = 归属强度 × 逻辑匹配度 |
| **宏观环境乘数** | 考虑系统性风险，宽信用期加仓、紧流动性期减仓 | MEDIUM | 货币 - 信用四象限判定，macro_multiplier 0.85-1.15 |
| **板块结构识别** | 聚焦/扩散/快速轮动，指导配置策略 | MEDIUM | 领涨集中度计算，替代人工分支划分 |
| **龙头/中军/跟风识别** | 明确个股在板块内的地位 | MEDIUM | 基于涨幅、市值、成交额自动判定 |
| **连续仓位函数** | 避免硬阈值断裂（0.30 vs 0.29 差异过大） | LOW | 连续函数替代离散矩阵，回测易调优 |
| **LLM 定性 + 锚点 + 规则引擎** | 平衡 AI 灵活性与规则确定性 | HIGH | LLM 只做识别与提取，不打分；评分由规则引擎计算 |
| **LLM 降级策略** | 服务不可用时系统可降级运行 | MEDIUM | 沿用上一日数据 + 自然衰减，系统降级为"市场层驱动" |
| **四维雷达图可视化** | 直观展示个股综合状态 | LOW | 逻辑受益度、市场强度、催化剂、板块强度 |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **实时行情推送** | 用户希望盘中实时提醒 | Phase 0.5 复杂度太高，且与"收盘后批量计算"定位冲突 | 明确边界：仅收盘后批量计算，不做实时 |
| **历史新闻批量回测** | 用户希望回测验证策略 | 历史新闻文本库不可得，批量调用 LLM 成本太高 | Phase 0.5 采用手工标注强度曲线 + 回放 |
| **板块敏感度矩阵** | 精细化调整板块对宏观的敏感度 | 31 行业 × 5 维度=155 参数，维护成本过高且无法适应风格切换 | 改用逻辑族敏感度（20 参数） |
| **估值安全度维度** | 用户习惯看 PE/PB 分位 | A 股估值周期性太强，易产生错误锚定（2020 新能源、2022 银行地产） | 不作为固定维度，用户可自行查看 |
| **自动交易执行** | 用户希望一键跟买 | 合规风险高，连接券商 API 复杂度大 | 仅提供推荐，不连接券商 API |
| **移动端 App** | 用户希望随时随地查看 | 开发成本 3 倍于 Web，MVP 阶段资源浪费 | Web 优先，移动 later |
| **精细分歧系数** | 用户希望量化逻辑分歧程度 | 未经回测验证，自由参数过多 | Phase 0.5 用"有无反向逻辑"简标替代 |
| **五状态机判定** | 更精细的市场状态划分 | 参数过多，回测易过拟合 | 三状态判定（weak/normal/overheated） |
| **离散仓位矩阵** | 用户习惯明确的档位 | 硬阈值断裂导致 0.30 vs 0.29 差异过大 | 连续仓位函数 |
| **板块分支映射表** | 人工划分板块分支 | 400+ 概念板块人工划分不现实 | 领涨集中度纯量价代理指标 |

## Feature Dependencies

```
[每日推荐列表]
    └──requires──> [个股综合评分]
                       └──requires──> [个股逻辑承接评分]
                       └──requires──> [个股市场雷达]
    └──requires──> [板块热度排行]
                       └──requires──> [板块市场雷达]
    └──requires──> [仓位建议]
                       └──requires──> [连续仓位函数]
                       └──requires──> [宏观环境乘数]

[事件计分板驱动]
    └──requires──> [LLM 逻辑识别与事件提取]
    └──requires──> [规则引擎计算逻辑强度]

[逻辑受益度量化]
    └──requires──> [个股 - 板块映射表]
    └──requires──> [暴露系数计算]
    └──requires──> [板块逻辑层净推力]

[龙头/中军/跟风识别]
    └──requires──> [个股市场雷达]
    └──requires──> [板块成分股数据]

[板块结构识别]
    └──requires──> [领涨集中度计算]
    └──requires──> [轮动速度计算]
```

### Dependency Notes

- **个股综合评分 requires 逻辑承接评分 + 市场雷达:** 综合分 = 50% logic + 50% market，两者缺一不可
- **逻辑承接评分 requires 个股 - 板块映射 + 暴露系数:** 暴露系数 = 归属强度 × 逻辑匹配度，需先有映射关系
- **仓位建议 requires 连续仓位函数 + 宏观乘数:** 仓位分 = (净推力 + 综合分 + 市场强度) × macro_multiplier
- **板块结构识别 requires 领涨集中度:** 纯量价计算，无需人工划分分支

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] **每日 Top 20 推荐列表** — 核心输出，含排名、代码、名称、综合分、仓位建议、地位标记
- [ ] **个股综合评分** — 逻辑分 + 市场分 50/50 加权，0-100 分展示
- [ ] **个股逻辑承接评分** — 多板块归属 + 暴露系数计算，输出 stock_logic_score
- [ ] **个股市场雷达** — 技术面 + 情绪面评分，sigmoid 归一化
- [ ] **板块市场雷达** — 技术面 + 情绪面，三状态判定（weak/normal/overheated）
- [ ] **板块逻辑层净推力** — 事件计分板规则引擎计算，净推力 + 有无反向标记
- [ ] **连续仓位函数** — 替代离散矩阵，2 个自由参数（权重、阈值）便于回测调优
- [ ] **宏观环境乘数** — 货币 - 信用四象限判定，macro_multiplier 0.85-1.15
- [ ] **龙头/中军/跟风识别** — 基于涨幅、市值、成交额自动判定
- [ ] **板块结构标记** — 领涨集中度计算，输出聚焦/扩散/快速轮动
- [ ] **基础交易约束检查** — 排除 ST、停牌、涨跌停不可交易状态
- [ ] **止损参考规则** — 主逻辑强度回撤>0.15 减仓、板块状态降为 weak 退出

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] **四维雷达图可视化** — 触发：用户反馈需要更直观的个股状态展示
- [ ] **LLM 降级策略** — 触发：LLM 服务不稳定时，系统需降级运行
- [ ] **手动覆盖功能** — 触发：用户希望修正归属强度、催化剂等标记
- [ ] **概念板块关键词库自动生成** — 触发：新板块频繁出现，人工维护成本过高
- [ ] **龙虎榜机构净买入标记** — 触发：Tushare top_inst 接口接入完成

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **历史新闻批量回测** — 需积累历史新闻文本库，Phase 2 实现
- [ ] **板块敏感度矩阵** — 逻辑族敏感度已够用，精细化待验证
- [ ] **精细分歧系数** — 需回测确定最优阈值，Phase 2 引入
- [ ] **实时行情推送** — 定位变更，需重新设计架构
- [ ] **自动交易执行** — 合规风险高，需评估
- [ ] **移动端 App** — Web 验证后再考虑

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 每日 Top 20 推荐列表 | HIGH | MEDIUM | P1 |
| 个股综合评分 | HIGH | MEDIUM | P1 |
| 个股逻辑承接评分 | HIGH | HIGH | P1 |
| 板块市场雷达 | HIGH | MEDIUM | P1 |
| 板块逻辑层净推力 | HIGH | HIGH | P1 |
| 连续仓位函数 | HIGH | LOW | P1 |
| 宏观环境乘数 | MEDIUM | MEDIUM | P1 |
| 龙头/中军/跟风识别 | MEDIUM | MEDIUM | P2 |
| 板块结构标记 | MEDIUM | LOW | P2 |
| 基础交易约束检查 | HIGH | LOW | P1 |
| 止损参考规则 | MEDIUM | LOW | P2 |
| 四维雷达图可视化 | MEDIUM | LOW | P2 |
| LLM 降级策略 | MEDIUM | MEDIUM | P2 |
| 手动覆盖功能 | LOW | MEDIUM | P3 |
| 概念板块关键词库自动生成 | MEDIUM | MEDIUM | P2 |
| 龙虎榜机构净买入标记 | MEDIUM | LOW | P2 |

**Priority key:**
- P1: Must have for launch (Phase 0.5 MVP 核心功能)
- P2: Should have, add when possible (Phase 0.5 后期或 Phase 1)
- P3: Nice to have, future consideration (Phase 2+)

## Competitor Feature Analysis

| Feature | 同花顺 iFinD | 东方财富 Choice | 我们的方案 |
|---------|--------------|-----------------|------------|
| **选股逻辑** | 条件选股（技术指标 + 基本面） | 条件选股 + 量化策略 | 事件计分板驱动，逻辑强度可解释 |
| **板块分析** | 行业/概念板块涨跌幅排行 | 概念板块热度、资金流向 | 板块市场雷达 + 逻辑净推力 + 结构识别 |
| **个股评分** | 无统一评分，多维数据展示 | 个股综合评级（机构一致预期） | 逻辑受益度 + 市场强度 50/50 加权 |
| **仓位建议** | 无 | 无 | 连续仓位函数输出重仓/半仓/轻仓/观察 |
| **逻辑归因** | 无 | 无 | 多逻辑并发识别，净推力计算 |
| **宏观环境** | 宏观数据展示 | 宏观数据展示 | 货币 - 信用四象限判定 + 全局乘数 |
| **回测能力** | 支持策略回测 | 支持策略回测 | Phase 0.5 手工标注强度曲线 + 回放 |
| **实时推送** | 支持 | 支持 | 不支持（收盘后批量计算） |
| **可视化** | 丰富图表 | 丰富图表 | 四维雷达图（逻辑、市场、催化剂、板块） |

## Sources

- 项目文档：`/Users/heyecheng/Program/llm/stock_logic/.planning/PROJECT.md`
- 需求文档：`/Users/heyecheng/Program/llm/stock_logic/REQUIREMENTS.md`
- 现有代码技能目录：`/Users/heyecheng/Program/llm/stock_logic/old/skills/sector-logic/README.md`
- efinance 库文档（A 股数据源）：Context7 `/micro-sheep/efinance`
- 同花顺、东方财富等竞品功能参考（基于训练数据）

---

*Feature research for: A 股量化选股系统 (Quantitative Stock Selection for A-Share Market)*
*Researched: 2026-04-19*
