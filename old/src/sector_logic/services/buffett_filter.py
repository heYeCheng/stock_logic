# -*- coding: utf-8 -*-
"""
BuffettFilter: qualitative filter for individual stocks.

Input:
  - Stock qualitative data (company description, management, financials, business model)
  - Skill files: stock/buffett-qualitative-filter.md

Process:
  1. Load Buffett filter rules
  2. Check 4 dimensions: moat, management, financial health, understandability
  3. Apply forced downgrade rules

Output:
  - buffett_result: pass/pass_with_concerns/fail
  - dimension_results with reasoning
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BuffettFilter:
    """
    Qualitative filter for individual stocks based on Buffett principles.
    """

    DIMENSIONS = ["moat", "management", "financial_health", "understandability"]
    DIMENSION_WEIGHTS = {
        "moat": 0.3,
        "management": 0.3,
        "financial_health": 0.25,
        "understandability": 0.15,
    }

    # Check thresholds from skill file
    MOAT_CHECKS = [
        "brand_premium", "cost_advantage", "network_effect",
        "switching_cost", "franchise_or_patent"
    ]
    MANAGEMENT_CHECKS = [
        "management_stability", "management_integrity", "management_focus",
        "incentive_alignment", "capital_allocation"
    ]
    FINANCIAL_CHECKS = [
        "debt_ratio", "operating_cashflow", "goodwill_risk",
        "receivable_risk", "inventory_risk"
    ]
    UNDERSTANDABILITY_CHECKS = [
        "simple_business_model", "clear_revenue_source",
        "within_circle_of_competence", "no_complex_related_transactions"
    ]

    def __init__(self, skill_loader=None, llm_client=None):
        self.skill_loader = skill_loader
        self.llm_client = llm_client

    async def filter(
        self,
        stock_code: str,
        stock_qualitative_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run Buffett qualitative filter.

        Args:
            stock_code: Stock ticker
            stock_qualitative_data: Qualitative data for the 4 dimensions

        Returns:
            Dict with final_result, dimension_results, reasoning
        """
        logger.info(f"[BuffettFilter] filtering {stock_code}")

        # If LLM available, use LLM-based filtering
        if self.llm_client:
            try:
                return await self._filter_with_llm(stock_code, stock_qualitative_data)
            except Exception as e:
                logger.warning(f"[BuffettFilter] LLM failed: {e}, falling back to rules")

        # Rule-based fallback
        return self._filter_with_rules(stock_code, stock_qualitative_data)

    async def _filter_with_llm(
        self,
        stock_code: str,
        stock_qualitative_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LLM-based Buffett filter (placeholder)."""
        # Build prompt from skill file and call LLM
        # For now, fall back to rules
        return self._filter_with_rules(stock_code, stock_qualitative_data)

    def _filter_with_rules(
        self,
        stock_code: str,
        stock_qualitative_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Rule-based Buffett filter."""
        dimension_results = {}

        # 1. Moat check
        dimension_results["moat"] = self._check_moat(stock_qualitative_data)

        # 2. Management check
        dimension_results["management"] = self._check_management(stock_qualitative_data)

        # 3. Financial health check
        dimension_results["financial_health"] = self._check_financial_health(stock_qualitative_data)

        # 4. Understandability check
        dimension_results["understandability"] = self._check_understandability(stock_qualitative_data)

        # Determine final result
        final_result = self._determine_final_result(dimension_results)

        return {
            "stock_code": stock_code,
            "final_result": final_result,
            "dimension_results": dimension_results,
            "forced_downgrade": final_result != "pass",
        }

    def _check_moat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check moat dimension."""
        checks_passed = 0
        reasons = []

        if data.get("brand_premium", False):
            checks_passed += 1
            reasons.append("品牌优势")
        if data.get("cost_advantage", False):
            checks_passed += 1
            reasons.append("成本优势")
        if data.get("network_effect", False):
            checks_passed += 1
            reasons.append("网络效应")
        if data.get("switching_cost", False):
            checks_passed += 1
            reasons.append("转换成本")
        if data.get("franchise_or_patent", False):
            checks_passed += 1
            reasons.append("特许经营权/专利")

        if checks_passed >= 2:
            result = "pass"
        elif checks_passed == 1:
            result = "pass_with_concerns"
        else:
            result = "fail"

        return {
            "result": result,
            "checks_passed": checks_passed,
            "total_checks": len(self.MOAT_CHECKS),
            "reasons": reasons,
        }

    def _check_management(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check management dimension."""
        checks_passed = 0
        reasons = []

        if data.get("management_stability", False):
            checks_passed += 1
            reasons.append("管理层稳定")
        if data.get("management_integrity", False):
            checks_passed += 1
            reasons.append("管理层诚信")
        if data.get("management_focus", False):
            checks_passed += 1
            reasons.append("主业专注")
        if data.get("incentive_alignment", False):
            checks_passed += 1
            reasons.append("股权激励合理")
        if data.get("capital_allocation", False):
            checks_passed += 1
            reasons.append("资本配置优秀")

        # Integrity issue = automatic fail
        if not data.get("management_integrity", False):
            result = "fail"
            reasons.append("存在诚信问题")
        elif checks_passed >= 4:
            result = "pass"
        elif checks_passed >= 2:
            result = "pass_with_concerns"
        else:
            result = "fail"

        return {
            "result": result,
            "checks_passed": checks_passed,
            "total_checks": len(self.MANAGEMENT_CHECKS),
            "reasons": reasons,
        }

    def _check_financial_health(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check financial health dimension."""
        checks_passed = 0
        reasons = []

        debt_ratio = data.get("debt_ratio")
        if debt_ratio is not None:
            if debt_ratio < 0.6 or data.get("is_financial_stock", False):
                checks_passed += 1
                reasons.append("负债率健康")
            else:
                reasons.append("负债率过高")

        if data.get("positive_operating_cashflow", False):
            checks_passed += 1
            reasons.append("经营现金流为正")
        else:
            reasons.append("经营现金流为负")

        goodwill_ratio = data.get("goodwill_to_equity")
        if goodwill_ratio is not None:
            if goodwill_ratio < 0.3:
                checks_passed += 1
                reasons.append("商誉风险可控")
            else:
                reasons.append("商誉减值风险")

        receivable_ratio = data.get("receivable_to_revenue")
        if receivable_ratio is not None:
            if receivable_ratio < 0.5:
                checks_passed += 1
                reasons.append("应收账款可控")
            else:
                reasons.append("应收账款过高")

        inventory_ratio = data.get("inventory_to_revenue")
        if inventory_ratio is not None:
            if inventory_ratio < 0.5:
                checks_passed += 1
                reasons.append("存货可控")
            else:
                reasons.append("存货减值风险")

        # Major impairment risk = automatic fail
        if goodwill_ratio is not None and goodwill_ratio > 0.5:
            result = "fail"
            reasons.append("存在重大减值风险")
        elif checks_passed >= 4:
            result = "pass"
        elif checks_passed >= 2:
            result = "pass_with_concerns"
        else:
            result = "fail"

        return {
            "result": result,
            "checks_passed": checks_passed,
            "total_checks": len(self.FINANCIAL_CHECKS),
            "reasons": reasons,
        }

    def _check_understandability(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check understandability dimension."""
        checks_passed = 0
        reasons = []

        if data.get("simple_business_model", False):
            checks_passed += 1
            reasons.append("业务模式简单易懂")
        else:
            reasons.append("业务模式复杂")

        top5_customer_ratio = data.get("top5_customer_revenue_ratio")
        if top5_customer_ratio is not None:
            if top5_customer_ratio < 0.5:
                checks_passed += 1
                reasons.append("收入来源分散")
            else:
                reasons.append("收入集中度过高")

        if data.get("within_competence_circle", False):
            checks_passed += 1
            reasons.append("在能力圈内")
        else:
            reasons.append("超出能力圈")

        if not data.get("complex_related_transactions", True):
            checks_passed += 1
            reasons.append("无复杂关联交易")
        else:
            reasons.append("存在复杂关联交易")

        # Complex related transactions = automatic fail
        if data.get("complex_related_transactions", False):
            result = "fail"
            reasons.append("存在复杂关联交易")
        elif checks_passed >= 3:
            result = "pass"
        elif checks_passed >= 2:
            result = "pass_with_concerns"
        else:
            result = "fail"

        return {
            "result": result,
            "checks_passed": checks_passed,
            "total_checks": len(self.UNDERSTANDABILITY_CHECKS),
            "reasons": reasons,
        }

    def _determine_final_result(self, dimension_results: Dict[str, Dict]) -> str:
        """
        Determine final result based on dimension results.

        Rules:
        - fail: any dimension is "fail"
        - pass: all dimensions at least "pass_with_concerns", and at least 2 are "pass"
        - pass_with_concerns: all at least "pass_with_concerns", but 0-1 "pass"
        """
        results = [d["result"] for d in dimension_results.values()]

        # Any fail → fail
        if "fail" in results:
            return "fail"

        pass_count = sum(1 for r in results if r == "pass")

        if pass_count >= 2:
            return "pass"
        else:
            return "pass_with_concerns"

    def apply_downgrade(self, buffett_result: str, tier: str) -> str:
        """
        Apply forced downgrade rules.

        Rules:
        - fail → "其余" regardless of original tier
        - pass_with_concerns → max "观察名单"
        - pass → no change
        """
        if buffett_result == "fail":
            return "其余"
        elif buffett_result == "pass_with_concerns":
            if tier == "重点关注":
                return "观察名单"
            return tier
        else:
            return tier
