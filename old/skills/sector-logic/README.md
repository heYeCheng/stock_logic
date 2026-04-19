# Sector Logic Skills

**Version**: 1.0
**Last Updated**: 2026-04-16

## 概述

本目录包含 Sector Logic Engine 使用的 skill 文件，分为三类：

1. **Logic Types** (`logic-types/`) — 逻辑类型定义（Markdown）
2. **Frameworks** (`frameworks/`) — 评估框架（JSON）
3. **Risk Templates** (`risk-templates/`) — 风险模板（JSON）

## 目录结构

```
~/.gstack/skills/sector-logic/
├── README.md                        # 本文件
├── logic-types/                     # 逻辑类型定义
│   ├── 产业趋势.md
│   ├── 政策驱动.md
│   ├── 供需周期.md
│   ├── 流动性.md
│   ├── 事件驱动.md
│   ├── 估值重构.md
│   ├── 成本反转.md
│   ├── 技术革命.md
│   ├── 竞争格局变化.md
│   └── 制度变革.md
├── frameworks/                      # 评估框架
│   ├── 产业趋势-framework.json
│   ├── 政策驱动-framework.json
│   ├── 供需周期-framework.json
│   ├── 流动性-framework.json
│   ├── 事件驱动-framework.json
│   ├── 估值重构-framework.json
│   ├── 成本反转-framework.json
│   ├── 技术革命-framework.json
│   ├── 竞争格局变化-framework.json
│   └── 制度变革-framework.json
└── risk-templates/                  # 风险模板
    ├── 产业趋势-risk.json
    ├── 政策驱动-risk.json
    ├── 供需周期-risk.json
    ├── 流动性-risk.json
    ├── 事件驱动-risk.json
    ├── 估值重构-risk.json
    ├── 成本反转-risk.json
    ├── 技术革命-risk.json
    ├── 竞争格局变化-risk.json
    └── 制度变革-risk.json
```

## Skill 文件说明

### Logic Types (logic-types/*.md)

每个逻辑类型的定义文件，包含：
- 核心定义（判定边界）
- 典型场景
- 持续时间
- 判定规则
- 对应的 framework 和 risk-templates 引用

### Frameworks (frameworks/*-framework.json)

每个逻辑类型的评估框架，包含：
- 5 个评估维度及其权重
- 每个维度的数据源
- 每个维度的 LLM 评分 prompt
- 版本号和元数据

### Risk Templates (risk-templates/*-risk.json)

每个逻辑类型的风险模板，包含：
- 5 个风险因素
- 每个风险的信号源
- LLM 触发判断 prompt
- 触发后的动作和建议

## 使用方式

代码通过 `SectorLogicSkillLoader` 加载 skill 文件：

```python
from src.sector_logic.skill_loader import SectorLogicSkillLoader

loader = SectorLogicSkillLoader()

# 加载逻辑类型定义
logic_type = loader.load_logic_type("产业趋势")

# 加载评估框架
framework = loader.load_framework("产业趋势")

# 加载风险模板
risk_template = loader.load_risk_template("产业趋势")

# 列出所有逻辑类型
categories = loader.list_logic_types()
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-04-16 | 初始版本 — 10 类逻辑类型、框架、风险模板 |
