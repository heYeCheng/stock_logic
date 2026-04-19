# -*- coding: utf-8 -*-
"""
LogicExtractor: extracts trading logic category from sector data.

Input:
  - Sector name
  - Sector data (price, volume, capital flow, news)
  - Skill files: logics/{category}/definition.md

Process:
  1. Analyze sector price/capital flow pattern
  2. Match against logic type definitions (10 categories)
  3. Use LLM for classification (preferred) or rule-based fallback

Output:
  - TradingLogic dict with:
    - logic_id, sector, title, description
    - category (one of 10 logic types)
    - logic_thesis_score, logic_price_score
    - status (emerging/dominant)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LogicExtractor:
    """
    Extracts trading logic category from sector data.

    Supports:
    - Rule-based classification (MVP)
    - LLM-based classification (future)
    """

    # 10 logic type categories
    LOGIC_CATEGORIES = [
        "产业趋势",
        "政策驱动",
        "供需周期",
        "流动性",
        "事件驱动",
        "估值重构",
        "成本反转",
        "技术革命",
        "竞争格局变化",
        "制度变革",
    ]

    def __init__(self, skill_loader, llm_client=None):
        self.skill_loader = skill_loader
        self.llm_client = llm_client
        self._logic_definitions = {}

    def _load_logic_definitions(self) -> Dict[str, Any]:
        """Load all logic type definitions."""
        if self._logic_definitions:
            return self._logic_definitions

        for category in self.LOGIC_CATEGORIES:
            logic_type = self.skill_loader.load_logic_type(category)
            if logic_type:
                self._logic_definitions[category] = {
                    "definition": logic_type.definition,
                    "typical_scenarios": logic_type.typical_scenarios,
                    "rules": logic_type.rules,
                }

        return self._logic_definitions

    async def extract(
        self,
        sector: str,
        d: date,
        sector_data: Dict[str, Any],
        macro_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Extract trading logic from sector data.

        Args:
            sector: Sector name
            d: Analysis date
            sector_data: Sector data (price, volume, capital flow, news)
            macro_context: Optional macro context

        Returns:
            TradingLogic dict
        """
        logger.info(f"[LogicExtractor] extracting logic for {sector} on {d.isoformat()}")

        # Try LLM-based extraction if available
        if self.llm_client:
            try:
                return await self._extract_with_llm(sector, d, sector_data, macro_context)
            except Exception as e:
                logger.warning(f"[LogicExtractor] LLM extraction failed: {e}, falling back to rules")

        # Rule-based fallback
        return self._extract_with_rules(sector, d, sector_data, macro_context)

    async def _extract_with_llm(
        self,
        sector: str,
        d: date,
        sector_data: Dict[str, Any],
        macro_context: Optional[Dict],
    ) -> Dict[str, Any]:
        """LLM-based logic extraction."""
        # Load logic definitions
        definitions = self._load_logic_definitions()

        # Build prompt
        prompt = self._build_llm_prompt(sector, d, sector_data, macro_context, definitions)

        # Call LLM (placeholder - actual implementation depends on LLM client)
        # llm_response = await self.llm_client.chat(prompt)
        # category = self._parse_llm_response(llm_response)

        # For now, fall back to rule-based
        return self._extract_with_rules(sector, d, sector_data, macro_context)

    def _build_llm_prompt(
        self,
        sector: str,
        d: date,
        sector_data: Dict[str, Any],
        macro_context: Optional[Dict],
        definitions: Dict[str, Any],
    ) -> str:
        """Build LLM prompt for logic classification."""
        sector_index = sector_data.get("sector_index", {})
        capital_flow = sector_data.get("capital_flow", {})
        news = sector_data.get("news_items", [])

        pct_chg = sector_index.get("pct_chg", 0)
        net_flow = capital_flow.get("net_flow", 0)

        prompt = f"""请分析 {sector} 板块的主导交易逻辑类型。

板块数据:
- 日期：{d.isoformat()}
- 涨跌幅：{pct_chg:.2f}%
- 资金净流入：{net_flow:.2f} 万元
- 新闻数量：{len(news)} 条

可选逻辑类型 (10 种):
"""
        for cat, defn in definitions.items():
            prompt += f"- {cat}: {defn['definition'][:50]}...\n"

        prompt += """
请从以上 10 种逻辑类型中选择最匹配的一种，并说明理由。
输出格式：{"category": "逻辑类型", "confidence": 0.0-1.0, "reasoning": "..."}
"""
        return prompt

    def _extract_with_rules(
        self,
        sector: str,
        d: date,
        sector_data: Dict[str, Any],
        macro_context: Optional[Dict],
    ) -> Dict[str, Any]:
        """Rule-based logic extraction (MVP fallback)."""
        sector_index = sector_data.get("sector_index", {})
        capital_flow = sector_data.get("capital_flow", {})
        news = sector_data.get("news_items", [])

        pct_chg = sector_index.get("pct_chg", 0)
        net_flow = capital_flow.get("net_flow", 0)

        # Classify based on price + capital flow pattern
        category, title, description, strength, confidence = self._classify_pattern(
            sector, pct_chg, net_flow, news
        )

        # Build TradingLogic dict
        logic = {
            "logic_id": f"logic_{d.isoformat()}_{sector.replace('/', '')}",
            "sector": sector,
            "title": title,
            "description": description,
            "category": category,
            "logic_thesis_score": round(strength, 4),
            "logic_price_score": round(min(1.0, max(0, (pct_chg + 5) / 10)), 4),
            "logic_strength": round(strength, 4),
            "logic_strength_trend": "increasing" if pct_chg > 0 else "declining" if pct_chg < -1 else "stable",
            "status": "dominant" if strength >= 0.5 else "emerging",
            "identified_date": d.isoformat(),
            "confidence": confidence,
        }

        logger.info(f"[LogicExtractor] {sector} -> {category} (strength={strength:.2f})")
        return logic

    def _classify_pattern(
        self,
        sector: str,
        pct_chg: float,
        net_flow: float,
        news: List[Dict],
    ) -> tuple:
        """
        Classify logic category from price/capital pattern.

        Returns:
            (category, title, description, strength, confidence)
        """
        # Pattern 1: Price up + Capital inflow → 供需周期 or 产业趋势
        if pct_chg > 0 and net_flow > 0:
            if pct_chg > 3 and net_flow > 5000:
                category = "供需周期"
                title = f"{sector} 供需改善逻辑"
                description = f"{sector} 价量齐升，资金大幅净流入"
                strength = 0.6 + min(0.2, pct_chg / 10) + min(0.2, net_flow / 10000)
                confidence = 0.75
            else:
                category = "产业趋势"
                title = f"{sector} 产业趋势逻辑"
                description = f"{sector} 温和上涨，资金净流入"
                strength = 0.5 + min(0.15, pct_chg / 10) + min(0.15, net_flow / 5000)
                confidence = 0.65

        # Pattern 2: Price up + Capital outflow → 估值重构
        elif pct_chg > 0 and net_flow <= 0:
            category = "估值重构"
            title = f"{sector} 估值修复逻辑"
            description = f"{sector} 价升量缩，资金净流出"
            strength = 0.4 + min(0.1, pct_chg / 10)
            confidence = 0.5

        # Pattern 3: Price down + Capital inflow → 估值重构 (抄底)
        elif pct_chg <= 0 and net_flow > 0:
            category = "估值重构"
            title = f"{sector} 左侧抄底逻辑"
            description = f"{sector} 价跌量进，资金逆势流入"
            strength = 0.45 + min(0.1, net_flow / 5000)
            confidence = 0.45

        # Pattern 4: Price down + Capital outflow → 竞争格局变化 or 成本反转
        else:
            if pct_chg < -3 and net_flow < -5000:
                category = "竞争格局变化"
                title = f"{sector} 竞争恶化逻辑"
                description = f"{sector} 价量齐跌，资金大幅流出"
                strength = max(0.2, 0.5 + pct_chg / 10)
                confidence = 0.6
            else:
                category = "成本反转"
                title = f"{sector} 成本压力逻辑"
                description = f"{sector} 温和下跌，资金流出"
                strength = max(0.3, 0.5 + pct_chg / 15)
                confidence = 0.5

        # News sentiment adjustment
        if news:
            positive_keywords = ["利好", "突破", "增长", "创新高", "景气", "爆发"]
            negative_keywords = ["利空", "下滑", "萎缩", "承压", "风险", "下跌"]

            pos_count = sum(1 for n in news if any(kw in (n.get("title", "") or "") for kw in positive_keywords))
            neg_count = sum(1 for n in news if any(kw in (n.get("title", "") or "") for kw in negative_keywords))

            if pos_count > neg_count + 2:
                strength = min(0.9, strength + 0.1)
                confidence = min(0.85, confidence + 0.1)
            elif neg_count > pos_count + 2:
                strength = max(0.1, strength - 0.1)
                confidence = min(0.85, confidence + 0.05)

        strength = max(0.1, min(0.9, strength))
        return category, title, description, strength, confidence
