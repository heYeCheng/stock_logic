# Requirements: 交易逻辑驱动的智能选股系统 (stock_logic)

**Defined**: 2026-04-19  
**Core Value**: 逻辑真值独立于价格 —— 通过事件计分板规则引擎计算逻辑强度，LLM 识别逻辑与提取事件但不打分；市场认知仅用量价数据，两者严格隔离，确保决策可解释、可回测。

## v1 Requirements (Phase 0.5 MVP)

Requirements for initial MVP release. Each maps to roadmap phases.

### L0 宏观环境层

- [ ] **MACRO-01**: 宏观五维度评分（流动性、增长、通胀成本、政策、全球）
- [ ] **MACRO-02**: 四象限判定（货币 - 信用框架）+ macro_multiplier 计算
- [ ] **MACRO-03**: 月度数据对齐与事件触发更新机制
- [ ] **MACRO-04**: 宏观数据不可用降级方案（macro_multiplier = 1.00）

### L1 板块逻辑层（事件计分板）

- [ ] **LOGIC-01**: LLM 逻辑识别与归类（输出 logic_id、方向、逻辑族、importance_level）
- [ ] **LOGIC-02**: LLM 事件提取（两阶段：事件提取 → logic_id 关联）
- [ ] **LOGIC-03**: 事件计分板规则引擎（加减分、自然衰减、有效期追踪）
- [ ] **LOGIC-04**: 事件去重与指纹校验
- [ ] **LOGIC-05**: 净推力计算 + 有无反向逻辑标记
- [ ] **LOGIC-06**: LLM 降级策略（服务不可用时沿用上一日 + 衰减）

### L2 板块市场层（纯量价）

- [ ] **MARKET-01**: 板块市场雷达图（技术面 + 情绪面评分）
- [ ] **MARKET-02**: 三状态判定（weak/normal/overheated）
- [ ] **MARKET-03**: 领涨集中度计算（替代分支分析）
- [ ] **MARKET-04**: 结构标记输出（聚焦/扩散/快速轮动）
- [ ] **MARKET-05**: Tushare 涨停板数据接入（limit_list、top_inst）

### L3 个股承接层

- [ ] **STOCK-01**: 个股 - 板块映射表（行业 + 概念板块归属）
- [ ] **STOCK-02**: 暴露系数计算（affiliation_strength × logic_match_score）
- [ ] **STOCK-03**: 关键词库自动生成（LLM 为新板块生成 5-8 个关键词）
- [ ] **STOCK-04**: 个股逻辑承接评分（stock_logic_score）
- [ ] **STOCK-05**: 个股市场雷达（技术面 + 情绪面）
- [ ] **STOCK-06**: 催化剂简化标记（强/中/无）
- [ ] **STOCK-07**: 龙头/中军/跟风识别
- [ ] **STOCK-08**: 个股综合评分（50% logic + 50% market）

### L4 执行决策层

- [ ] **EXEC-01**: 连续仓位函数（替代离散矩阵）
- [ ] **EXEC-02**: A 股交易约束检查（涨跌停、停牌、追高风险）
- [ ] **EXEC-03**: 个股推荐标记（逻辑受益股/关联受益股/情绪跟风股）
- [ ] **EXEC-04**: 止损与持有决策规则

### Web 界面

- [ ] **WEB-01**: FastAPI REST API（推荐列表、个股详情、宏观概览）
- [ ] **WEB-02**: React 前端（个股卡片、雷达图、逻辑摘要）
- [ ] **WEB-03**: 手动覆盖功能（用户可修正 strength、归属强度等标记）
- [ ] **WEB-04**: 锚点配置管理界面（YAML 文件编辑与版本控制）

### 基础设施

- [ ] **INFRA-01**: MySQL 数据库设计与迁移（events、logics、stocks 等表）
- [ ] **INFRA-02**: 定时任务调度（每日收盘后批量计算）
- [ ] **INFRA-03**: 数据源接入（Tushare、东方财富、akshare）
- [ ] **INFRA-04**: 日志与监控（LLM 调用、数据源健康检查）

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### 回测引擎

- **BACKTEST-01**: 历史新闻文本库批量 LLM 事件提取
- **BACKTEST-02**: 手工标注强度曲线导入工具
- **BACKTEST-03**: 参数网格搜索与回测报告
- **BACKTEST-04**: 消融实验框架（单变量测试）

### 高级功能

- **ADVANCED-01**: 实时行情推送与盘中监控
- **ADVANCED-02**: 券商 API 对接与自动交易
- **ADVANCED-03**: 移动端 App（iOS/Android）
- **ADVANCED-04**: 板块敏感度矩阵（逻辑族 × 5 维度）
- **ADVANCED-05**: 估值安全度维度（需解决周期性问题）

### 数据源扩展

- **DATA-01**: 投研萝卜接口接入
- **DATA-02**: 雪球深度爬虫（舆情分析）
- **DATA-03**: 机构研报数据库
- **DATA-04**: 北向资金实时数据

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| 实时行情推送 | Phase 0.5 仅收盘后批量计算，降低复杂度 |
| 移动端 App | Web 优先，移动 later |
| 自动交易执行 | 仅提供推荐，不连接券商 API（合规风险） |
| 历史新闻批量回测 | Phase 0.5 采用手工标注强度曲线，Phase 2 实现自动化 |
| 板块敏感度矩阵 | 155 个参数维护成本过高，改用逻辑族映射（20 个参数） |
| 估值安全度维度 | A 股估值周期性太强，易产生错误锚定 |
| 五状态机 | 简化为三状态判定（weak/normal/overheated） |
| 离散决策矩阵 | 改用连续仓位函数，减少硬阈值断裂 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MACRO-01 | Phase 1 | Pending |
| MACRO-02 | Phase 1 | Pending |
| MACRO-03 | Phase 1 | Pending |
| MACRO-04 | Phase 1 | Pending |
| LOGIC-01 | Phase 2 | Pending |
| LOGIC-02 | Phase 2 | Pending |
| LOGIC-03 | Phase 2 | Pending |
| LOGIC-04 | Phase 2 | Pending |
| LOGIC-05 | Phase 2 | Pending |
| LOGIC-06 | Phase 2 | Pending |
| MARKET-01 | Phase 3 | Pending |
| MARKET-02 | Phase 3 | Pending |
| MARKET-03 | Phase 3 | Pending |
| MARKET-04 | Phase 3 | Pending |
| MARKET-05 | Phase 3 | Pending |
| STOCK-01 | Phase 4 | Pending |
| STOCK-02 | Phase 4 | Pending |
| STOCK-03 | Phase 4 | Pending |
| STOCK-04 | Phase 4 | Pending |
| STOCK-05 | Phase 4 | Pending |
| STOCK-06 | Phase 4 | Pending |
| STOCK-07 | Phase 4 | Pending |
| STOCK-08 | Phase 4 | Pending |
| EXEC-01 | Phase 5 | Pending |
| EXEC-02 | Phase 5 | Pending |
| EXEC-03 | Phase 5 | Pending |
| EXEC-04 | Phase 5 | Pending |
| WEB-01 | Phase 6 | Pending |
| WEB-02 | Phase 6 | Pending |
| WEB-03 | Phase 6 | Pending |
| WEB-04 | Phase 6 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |

**Coverage**:
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-19*
*Last updated: 2026-04-19 after initial definition*
