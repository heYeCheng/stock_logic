# 交易逻辑驱动的智能选股系统 (stock_logic)

## What This Is

一个基于**多逻辑并发、事件计分板驱动**的 A 股波段选股决策系统。系统通过四层架构（宏观环境 → 板块逻辑 → 板块市场 → 个股承接）识别逻辑受益股，输出每日 Top 20 推荐列表与仓位建议。

**技术栈**：FastAPI + React + MySQL，Python 后端提供 REST API 与定时任务调度。

**目标用户**：个人投资者与交易员，追求 3-20 交易日波段收益。

## Core Value

**逻辑真值独立于价格** —— 通过事件计分板规则引擎计算逻辑强度，由 LLM 识别逻辑与提取事件，但不打分；市场认知仅用量价数据，两者严格隔离，确保决策可解释、可回测。

## Requirements

### Validated

(None yet — ship to validate)

### Active

#### L0 宏观环境层
- [ ] **MACRO-01**: 宏观五维度评分（流动性、增长、通胀成本、政策、全球）
- [ ] **MACRO-02**: 四象限判定（货币 - 信用框架）+ macro_multiplier 计算
- [ ] **MACRO-03**: 月度数据对齐与事件触发更新机制
- [ ] **MACRO-04**: 宏观数据不可用降级方案（macro_multiplier = 1.00）

#### L1 板块逻辑层（事件计分板）
- [ ] **LOGIC-01**: LLM 逻辑识别与归类（输出 logic_id、方向、逻辑族、importance_level）
- [ ] **LOGIC-02**: LLM 事件提取（两阶段：事件提取 → logic_id 关联）
- [ ] **LOGIC-03**: 事件计分板规则引擎（加减分、自然衰减、有效期追踪）
- [ ] **LOGIC-04**: 事件去重与指纹校验
- [ ] **LOGIC-05**: 净推力计算 + 有无反向逻辑标记
- [ ] **LOGIC-06**: LLM 降级策略（服务不可用时沿用上一日 + 衰减）

#### L2 板块市场层（纯量价）
- [ ] **MARKET-01**: 板块市场雷达图（技术面 + 情绪面评分）
- [ ] **MARKET-02**: 三状态判定（weak/normal/overheated）
- [ ] **MARKET-03**: 领涨集中度计算（替代分支分析）
- [ ] **MARKET-04**: 结构标记输出（聚焦/扩散/快速轮动）
- [ ] **MARKET-05**: Tushare 涨停板数据接入（limit_list、top_inst）

#### L3 个股承接层
- [ ] **STOCK-01**: 个股 - 板块映射表（行业 + 概念板块归属）
- [ ] **STOCK-02**: 暴露系数计算（affiliation_strength × logic_match_score）
- [ ] **STOCK-03**: 关键词库自动生成（LLM 为新板块生成 5-8 个关键词）
- [ ] **STOCK-04**: 个股逻辑承接评分（stock_logic_score）
- [ ] **STOCK-05**: 个股市场雷达（技术面 + 情绪面）
- [ ] **STOCK-06**: 催化剂简化标记（强/中/无）
- [ ] **STOCK-07**: 龙头/中军/跟风识别
- [ ] **STOCK-08**: 个股综合评分（50% logic + 50% market）

#### L4 执行决策层
- [ ] **EXEC-01**: 连续仓位函数（替代离散矩阵）
- [ ] **EXEC-02**: A 股交易约束检查（涨跌停、停牌、追高风险）
- [ ] **EXEC-03**: 个股推荐标记（逻辑受益股/关联受益股/情绪跟风股）
- [ ] **EXEC-04**: 止损与持有决策规则

#### Web 界面
- [ ] **WEB-01**: FastAPI REST API（推荐列表、个股详情、宏观概览）
- [ ] **WEB-02**: React 前端（个股卡片、雷达图、逻辑摘要）
- [ ] **WEB-03**: 手动覆盖功能（用户可修正 strength、归属强度等标记）
- [ ] **WEB-04**: 锚点配置管理界面（YAML 文件编辑与版本控制）

#### 基础设施
- [ ] **INFRA-01**: MySQL 数据库设计与迁移（events、logics、stocks 等表）
- [ ] **INFRA-02**: 定时任务调度（每日收盘后批量计算）
- [ ] **INFRA-03**: 数据源接入（Tushare、东方财富、akshare）
- [ ] **INFRA-04**: 日志与监控（LLM 调用、数据源健康检查）

### Out of Scope

- **实时行情推送** —— Phase 0.5 仅收盘后批量计算，不做实时
- **移动端 App** —— Web 优先，移动 later
- **自动交易执行** —— 仅提供推荐，不连接券商 API
- **历史新闻批量回测** —— Phase 0.5 采用手工标注强度曲线，Phase 2 实现自动化
- **板块敏感度矩阵** —— 155 个参数维护成本过高，改用逻辑族映射（20 个参数）
- **估值安全度维度** —— A 股估值周期性太强，易产生错误锚定

## Context

**现有代码状态**：
- `old/` 目录包含已有实现（FastAPI API、数据源、analyzer、bot 等）
- 代码质量不佳需重新设计，但可参考数据源接入、API 结构等
- 已有 skills/sector-logic 目录包含 10 类逻辑类型定义、评估框架、风险模板

**技术债务**：
- 现有代码未实现事件计分板架构
- LLM 输出未采用"定性 + 锚点 + 规则引擎"模式
- 市场层与逻辑层数据隔离不严格

**数据源优先级**：
1. tushare（Pro API，需 token）
2. efinance（东方财富，最高优先级）
2. akshare（东方财富爬虫）
4. pytdx（通达信行情）
5. baostock（证券宝）
6. 投研萝卜
7. 雪球

## Constraints

- **技术栈**：FastAPI + React + MySQL（用户指定）
- **数据源**：优先使用已接入的 Tushare 和东方财富接口
- **开发周期**：Phase 0.5 MVP 聚焦核心功能，砍掉复杂模块
- **回测需求**：所有参数需支持配置化，便于后续回测调优

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 事件计分板规则引擎驱动 | LLM 打分主观性强，规则引擎可解释、可回测 | ✓ Good |
| LLM 定性 + 锚点 + 规则引擎 | 平衡 AI 灵活性与规则确定性 | — Pending |
| 连续仓位函数替代离散矩阵 | 硬阈值断裂导致 0.30 vs 0.29 差异过大 | — Pending |
| 三状态判定替代五状态机 | 减少自由参数，简化回测 | — Pending |
| 领涨集中度替代分支映射表 | 400+ 概念板块人工划分不现实 | ✓ Good |
| 手工标注回测方案（Phase 0.5） | 历史新闻文本库不可得，批量调用 LLM 成本太高 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-19 after initialization*
