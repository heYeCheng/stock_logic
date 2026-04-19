# -*- coding: utf-8 -*-
"""
MacroAnalyzer: analyzes macro environment and produces macro_thesis_score.

Phase 2.5 Enhanced:
- 5-dimension evaluation: liquidity/cycle/inflation/policy/global
- Rule-based scoring for numeric indicators (evaluation-framework.json v2)
- LLM for policy_direction only (text interpretation needed)
- Output: macro_radar (5 dims), cycle_position, leading_signals integration

Input:
  - Macro data snapshot (China + US + Global + derived_indicators + trend_analysis)
  - Polymarket prediction data
  - Skill files: macro/evaluation-framework.json, macro/state-classification.json

Process:
  1. Load macro evaluation framework from skill file
  2. Evaluate each of 5 dimensions using scoring rules (mostly rule-based)
  3. Compute weighted macro_thesis_score (0-1)
  4. Classify macro_state (loose/neutral/tight)
  5. Integrate cycle_position and leading_signals from collector

Output:
  - macro_thesis_score: 0-1 (higher = more favorable for stocks)
  - macro_state: "loose" | "neutral" | "tight"
  - macro_radar: {liquidity_environment: 0-10, ...}  (5 dimensions)
  - summary: Human-readable summary
  - cycle_position: from collector (growth/liquidity/quadrant)
  - leading_signals: from collector
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MacroAnalyzer:
    """
    Analyzes macro environment and produces macro_thesis_score.

    Phase 2.5: 5-dimension evaluation with rule-based scoring
    (except policy_direction which uses LLM for text interpretation).

    Supports:
    - Rule-based evaluation (preferred for numeric indicators)
    - LLM-based evaluation (for policy_direction text interpretation)
    - Rule-based fallback (when LLM unavailable)
    """

    def __init__(self, skill_loader, llm_client=None, datastore=None):
        self.skill_loader = skill_loader
        self.llm_client = llm_client
        self.datastore = datastore
        self._framework = None
        self._state_config = None

    def _load_framework(self) -> Dict[str, Any]:
        """Load macro evaluation framework from skill file."""
        if self._framework:
            return self._framework

        try:
            framework = self.skill_loader._load_json_model(
                "macro/evaluation-framework.json",
                type("MockModel", (), {"__init__": lambda self, **kwargs: setattr(self, "__dict__", kwargs)})
            )
            if framework:
                self._framework = framework.__dict__
                return self._framework
        except Exception:
            pass

        skill_dir = self.skill_loader.skill_dir
        framework_path = skill_dir / "macro" / "evaluation-framework.json"
        if framework_path.exists():
            self._framework = json.loads(framework_path.read_text(encoding="utf-8"))
        else:
            self._framework = {"dimensions": []}

        return self._framework

    def _load_state_config(self) -> Dict[str, Any]:
        """Load macro state classification config from skill file."""
        if self._state_config:
            return self._state_config

        try:
            config = self.skill_loader._load_json_model(
                "macro/state-classification.json",
                type("MockModel", (), {"__init__": lambda self, **kwargs: setattr(self, "__dict__", kwargs)})
            )
            if config:
                self._state_config = config.__dict__
                return self._state_config
        except Exception:
            pass

        skill_dir = self.skill_loader.skill_dir
        config_path = skill_dir / "macro" / "state-classification.json"
        if config_path.exists():
            self._state_config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self._state_config = {"state_classification": {}}

        return self._state_config

    async def analyze(self, macro_data: Dict[str, Any], polymarket_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run macro analysis (Phase 2.5 enhanced).

        Args:
            macro_data: Macro snapshot from MacroCollector (with Phase 2.5 fields)
            polymarket_data: Polymarket data (optional, merged into macro_data)

        Returns:
            Dict with macro_thesis_score, macro_state, macro_radar (5 dims),
            summary, cycle_position, leading_signals
        """
        logger.info("[MacroAnalyzer] starting macro analysis (Phase 2.5)")

        # Merge Polymarket data
        if polymarket_data:
            macro_data.setdefault("global", {})["polymarket"] = polymarket_data

        # Load skill configs
        framework = self._load_framework()
        state_config = self._load_state_config()

        # Evaluate each of the 5 dimensions
        macro_radar = await self._evaluate_5_dimensions(macro_data, framework)

        # Compute weighted score
        macro_thesis_score = self._compute_weighted_score(macro_radar, framework)

        # Classify macro state
        macro_state = self._classify_state(macro_thesis_score, state_config)

        # Generate summary
        summary = self._generate_summary(
            macro_thesis_score, macro_state, macro_radar,
            macro_data.get("cycle_position"),
            macro_data.get("leading_signals", []),
        )

        result = {
            "macro_thesis_score": round(macro_thesis_score, 4),
            "macro_state": macro_state,
            "macro_radar": macro_radar,
            "summary": summary,
            "snapshot_date": macro_data.get("snapshot_date", date.today().isoformat()),
            "cycle_position": macro_data.get("cycle_position", {}),
            "leading_signals": macro_data.get("leading_signals", []),
            "trend_analysis": macro_data.get("trend_analysis", {}),
            "derived_indicators": macro_data.get("derived_indicators", {}),
        }

        logger.info(
            f"[MacroAnalyzer] macro_thesis_score={macro_thesis_score:.2f}, "
            f"state={macro_state}, "
            f"cycle={result['cycle_position'].get('quadrant', 'unknown')}"
        )
        return result

    # =========================================================================
    # Phase 2.5: 5-Dimension Evaluation
    # =========================================================================

    async def _evaluate_5_dimensions(
        self, macro_data: Dict, framework: Dict
    ) -> Dict[str, float]:
        """
        Evaluate all 5 macro dimensions.

        Returns dict of {dimension_name: score_0_to_10}.
        """
        china = macro_data.get("china", {})
        us = macro_data.get("us", {})
        global_data = macro_data.get("global", {})
        derived = macro_data.get("derived_indicators", {})
        trend = macro_data.get("trend_analysis", {})

        radar = {}

        # 1. 流动性环境 (liquidity_environment)
        radar["liquidity_environment"] = self._evaluate_liquidity(
            china, derived, trend
        )

        # 2. 经济周期位置 (economic_cycle_position)
        radar["economic_cycle_position"] = self._evaluate_economic_cycle(
            china, derived, trend
        )

        # 3. 通胀与成本 (inflation_and_cost)
        radar["inflation_and_cost"] = self._evaluate_inflation(
            china, derived, trend
        )

        # 4. 政策方向 (policy_direction)
        radar["policy_direction"] = await self._evaluate_policy(
            china, global_data
        )

        # 5. 全球联动 (global_linkage)
        radar["global_linkage"] = self._evaluate_global_linkage(
            us, global_data, derived
        )

        return radar

    # --- Dimension 1: 流动性环境 ---

    def _evaluate_liquidity(
        self, china: Dict, derived: Dict, trend: Dict
    ) -> float:
        """
        流动性环境评分 (0-10).

        Indicators:
        - M1-M2 剪刀差: >2%→9-10, 0-2%→6-8, -2-0%→4-6, <-2%→0-3
        - Shibor 期限结构: >0.8%→7-10, 0.5-0.8%→5-7, <0.5%→0-5
        - 社融存量增速: >10%→8-10, 8-10%→6-8, <8%→0-6
        - Shibor-Hibor 利差: <0.2%→8-10, 0.2-0.5%→5-8, >0.5%→0-5
        """
        scores = []

        # M1-M2 剪刀差
        m1m2 = derived.get("m1_m2_scissors", {}).get("current")
        if m1m2 is not None:
            if m1m2 > 2.0:
                scores.append(9.5)
            elif m1m2 > 0.5:
                scores.append(7.0)
            elif m1m2 > -0.5:
                scores.append(5.0)
            elif m1m2 > -2.0:
                scores.append(3.0)
            else:
                scores.append(1.5)

        # Shibor 期限结构 slope
        shibor_slope = derived.get("shibor_term_structure", {}).get("slope")
        if shibor_slope is not None:
            # Slope is (1y - overnight) / 365, typically ~0.003-0.009
            # Thresholds: steep > 0.008, normal 0.005-0.008, flat 0.002-0.005
            if shibor_slope > 0.008:
                scores.append(8.5)
            elif shibor_slope > 0.005:
                scores.append(6.0)
            else:
                scores.append(2.5)

        # 社融存量增速
        sf_growth = derived.get("social_financing_growth", {}).get("stock_yoy")
        if sf_growth is not None:
            if sf_growth > 10.0:
                scores.append(9.0)
            elif sf_growth > 8.0:
                scores.append(7.0)
            else:
                scores.append(3.0)

        # Shibor-Hibor 利差
        sh_hibor = derived.get("shibor_hibor_spread", {}).get("current")
        if sh_hibor is not None:
            if sh_hibor < 0.2:
                scores.append(9.0)
            elif sh_hibor < 0.5:
                scores.append(6.5)
            else:
                scores.append(2.5)

        # Fallback: use china_score if no derived indicators available
        if not scores:
            shibor_on = china.get("shibor_overnight")
            if shibor_on:
                return 7.0 if shibor_on < 1.8 else (5.0 if shibor_on < 2.5 else 3.0)
            return 5.0

        return sum(scores) / len(scores)

    # --- Dimension 2: 经济周期位置 ---

    def _evaluate_economic_cycle(
        self, china: Dict, derived: Dict, trend: Dict
    ) -> float:
        """
        经济周期位置评分 (0-10).

        Indicators:
        - PMI 领先指数: >3→8-10, 1-3→6-8, -1-1→4-6, <-1→0-4
        - PMI 库存周期相位 (based on production vs inventory)
        """
        scores = []

        # PMI 领先指数 (new_orders - inventory)
        pmi_leading = derived.get("pmi_leading_index", {}).get("current")
        if pmi_leading is not None:
            if pmi_leading > 3.0:
                scores.append(9.0)
            elif pmi_leading > 1.0:
                scores.append(7.0)
            elif pmi_leading > -1.0:
                scores.append(5.0)
            else:
                scores.append(2.0)

        # PMI 库存周期相位 (using raw PMI sub-indicators)
        pmi_new_orders = china.get("pmi_new_orders")
        pmi_inventory = china.get("pmi_inventory")
        if pmi_new_orders is not None and pmi_inventory is not None:
            if pmi_new_orders > 50 and pmi_inventory < 50:
                # 主动补库存 = 复苏期
                scores.append(9.0)
            elif pmi_new_orders > 50 and pmi_inventory > 50:
                # 被动去库存 = 过热期
                scores.append(7.0)
            elif pmi_new_orders < 50 and pmi_inventory > 50:
                # 被动补库存 = 滞胀期
                scores.append(3.0)
            elif pmi_new_orders < 50 and pmi_inventory < 50:
                # 主动去库存 = 衰退期
                scores.append(2.0)

        # Fallback: use raw PMI
        if not scores:
            pmi = china.get("pmi")
            if pmi is not None:
                if pmi > 51:
                    scores.append(8.0)
                elif pmi > 50:
                    scores.append(6.0)
                elif pmi > 49:
                    scores.append(4.0)
                else:
                    scores.append(2.0)

        if not scores:
            return 5.0

        return sum(scores) / len(scores)

    # --- Dimension 3: 通胀与成本 ---

    def _evaluate_inflation(
        self, china: Dict, derived: Dict, trend: Dict
    ) -> float:
        """
        通胀与成本评分 (0-10). Higher = lower cost pressure.

        Indicators:
        - PPI-CPI 剪刀差: <-1%→8-10, -1-1%→5-8, >1%→0-5
        - PPI 产业链传导 (production vs consumer goods PPI)
        - PMI 价格指数 (purchase vs ex-factory price)
        """
        scores = []

        # PPI-CPI 剪刀差
        ppi_cpi = derived.get("ppi_cpi_scissors", {}).get("current")
        if ppi_cpi is not None:
            if ppi_cpi < -1.0:
                scores.append(9.0)
            elif ppi_cpi < 1.0:
                scores.append(6.5)
            else:
                scores.append(2.5)

        # PPI 产业链传导 (生产资料 vs 生活资料)
        ppi_mp = china.get("ppi_mp_yoy")
        ppi_cg = china.get("ppi_cg_yoy")
        if ppi_mp is not None and ppi_cg is not None:
            gap = ppi_mp - ppi_cg
            if gap < 1.0:
                scores.append(8.5)
            elif gap < 3.0:
                scores.append(5.5)
            else:
                scores.append(2.0)

        # PMI 价格指数 (购进价格 vs 出厂价格)
        pmi_purchase = china.get("pmi_purchase_price")
        pmi_ex_factory = china.get("pmi_ex_factory_price")
        if pmi_purchase is not None and pmi_ex_factory is not None:
            price_gap = pmi_purchase - pmi_ex_factory
            if price_gap < 2:
                scores.append(8.5)
            elif price_gap < 5:
                scores.append(5.5)
            else:
                scores.append(2.0)

        # Fallback: use raw CPI/PPI
        if not scores:
            cpi = china.get("cpi_yoy")
            ppi = china.get("ppi_yoy")
            if cpi is not None and ppi is not None:
                if 1 < cpi < 3 and -2 < ppi < 2:
                    scores.append(7.0)
                elif cpi > 4 or ppi > 5:
                    scores.append(2.0)
                elif cpi < 0 or ppi < -3:
                    scores.append(3.0)
                else:
                    scores.append(5.0)

        if not scores:
            return 5.0

        return sum(scores) / len(scores)

    # --- Dimension 4: 政策方向 ---

    async def _evaluate_policy(self, china: Dict, global_data: Dict) -> float:
        """
        政策方向评分 (0-10).

        Indicators:
        - 高层会议定调 (LLM 评估政策基调)
        - 部委表态 (LLM 评估政策密集度与方向)
        - 实体融资成本 (规则: 利率 <4%→8-10, 4-5%→5-8, >5%→0-5)

        Phase 2.5: LLM for text interpretation, rules for numeric.
        """
        scores = []

        # 实体融资成本 (rule-based)
        # Use Shibor as proxy for financing cost
        shibor_1y = china.get("shibor_1y")
        shibor_3m = china.get("shibor_3m")
        financing_cost = shibor_1y or shibor_3m
        if financing_cost is not None:
            if financing_cost < 4.0:
                scores.append(9.0)
            elif financing_cost < 5.0:
                scores.append(6.5)
            else:
                scores.append(2.5)

        # Policy text interpretation (LLM-based, deferred if no client)
        if self.llm_client:
            llm_score = await self._evaluate_policy_with_llm(china, global_data)
            if llm_score is not None:
                scores.append(llm_score)

        # Fallback: neutral if no data
        if not scores:
            return 5.0

        return sum(scores) / len(scores)

    async def _evaluate_policy_with_llm(
        self, china: Dict, global_data: Dict
    ) -> Optional[float]:
        """Use LLM to evaluate policy direction from text data."""
        # TODO: Implement LLM-based policy evaluation
        # This would analyze government meeting notes, ministry statements, etc.
        # For now, return None to skip LLM evaluation
        return None

    # --- Dimension 5: 全球联动 ---

    def _evaluate_global_linkage(
        self, us: Dict, global_data: Dict, derived: Dict
    ) -> float:
        """
        全球联动评分 (0-10).

        Indicators:
        - 美国宏观: Fed Rate/Treasury/ISM/Nonfarm
          Fed Rate ↓→8-10, 持平→5-8, ↑→0-5
        - Polymarket 预测: 风险概率 <30%→8-10, 30-50%→5-8, >50%→0-5
        - 关税风险: 下降/概率<30%→8-10, 持平→5-8, 上升→0-5
        """
        scores = []

        # US: Fed Funds Rate
        fed_rate = us.get("fed_funds_rate")
        if fed_rate is not None:
            if fed_rate < 3.0:
                scores.append(9.0)
            elif fed_rate < 4.0:
                scores.append(7.0)
            elif fed_rate < 5.0:
                scores.append(5.0)
            else:
                scores.append(2.0)

        # US: Treasury 10Y
        treasury_10y = us.get("treasury_10y")
        if treasury_10y is not None:
            if treasury_10y < 3.5:
                scores.append(8.5)
            elif treasury_10y < 4.5:
                scores.append(6.0)
            else:
                scores.append(2.5)

        # US: ISM PMI
        ism_pmi = us.get("ism_pmi")
        if ism_pmi is not None:
            if ism_pmi > 55:
                scores.append(8.0)
            elif ism_pmi > 50:
                scores.append(6.0)
            else:
                scores.append(3.0)

        # Global: Geopolitical risk
        geo_risk = global_data.get("geopolitical_risk", "normal")
        if geo_risk == "normal":
            scores.append(8.0)
        elif geo_risk == "elevated":
            scores.append(4.0)
        elif geo_risk == "severe":
            scores.append(1.0)

        # Global: Tariff risk
        tariff_risk = global_data.get("tariff_risk", "normal")
        if tariff_risk == "normal":
            scores.append(8.0)
        elif tariff_risk == "elevated":
            scores.append(4.0)
        elif tariff_risk == "severe":
            scores.append(1.0)

        # Fallback
        if not scores:
            return 5.0

        return sum(scores) / len(scores)

    # =========================================================================
    # Weighted Score & Classification
    # =========================================================================

    def _compute_weighted_score(
        self, macro_radar: Dict[str, float], framework: Dict
    ) -> float:
        """Compute weighted macro_thesis_score (0-1) from 5-dimension radar."""
        dimensions = framework.get("dimensions", [])

        # Build weight lookup from framework
        weights = {}
        for dim in dimensions:
            dim_name = dim.get("name", "")
            weight = dim.get("weight", 0.0)
            weights[dim_name] = weight

        # If framework has 5 dimensions, use their weights
        # Otherwise, use default Phase 2.5 weights
        if len(weights) >= 5:
            total_score = 0.0
            total_weight = 0.0
            for dim_name, weight in weights.items():
                score = macro_radar.get(dim_name, 5.0)
                total_score += score * weight
                total_weight += weight
            if total_weight == 0:
                return 0.5
            return (total_score / total_weight) / 10.0

        # Default Phase 2.5 weights
        default_weights = {
            "liquidity_environment": 0.25,
            "economic_cycle_position": 0.25,
            "inflation_and_cost": 0.20,
            "policy_direction": 0.15,
            "global_linkage": 0.15,
        }

        total_score = sum(
            macro_radar.get(k, 5.0) * v for k, v in default_weights.items()
        )
        return total_score / 10.0

    def _classify_state(self, macro_thesis_score: float, state_config: Dict) -> str:
        """Classify macro_state based on score."""
        state_class = state_config.get("state_classification", {})

        loose = state_class.get("loose", {})
        if macro_thesis_score >= loose.get("min_score", 0.7):
            return "loose"

        tight = state_class.get("tight", {})
        if macro_thesis_score <= tight.get("max_score", 0.4):
            return "tight"

        return "neutral"

    def _generate_summary(
        self,
        macro_thesis_score: float,
        macro_state: str,
        macro_radar: Dict[str, float],
        cycle_position: Optional[Dict],
        leading_signals: List[Dict],
    ) -> str:
        """Generate human-readable summary (Phase 2.5 enhanced)."""
        state_cn = "宽松" if macro_state == "loose" else "紧缩" if macro_state == "tight" else "中性"

        # Find strongest and weakest dimensions
        if macro_radar:
            strongest = max(macro_radar, key=macro_radar.get)
            weakest = min(macro_radar, key=macro_radar.get)
            strongest_cn = _dim_name_cn(strongest)
            weakest_cn = _dim_name_cn(weakest)
        else:
            strongest_cn = "未知"
            weakest_cn = "未知"

        # Cycle position
        quadrant = cycle_position.get("quadrant", "未知") if cycle_position else "未知"

        summary = (
            f"宏观环境：{state_cn}（得分：{macro_thesis_score:.2f}）| "
            f"周期位置：{quadrant} | "
            f"最强维度：{strongest_cn}（{macro_radar.get(strongest, 0):.1f}）| "
            f"最弱维度：{weakest_cn}（{macro_radar.get(weakest, 0):.1f}）"
        )

        if leading_signals:
            signal_summary = "; ".join(
                f"{s['indicator']}: {s.get('prediction', '')}"
                for s in leading_signals[:2]
            )
            summary += f" | 领先信号: {signal_summary}"

        return summary

    async def needs_update(self, d: date, last_update_date: Optional[date], event_triggered: bool) -> bool:
        """
        Check if macro analysis needs to be re-run.
        """
        if event_triggered:
            logger.info("[MacroAnalyzer] event trigger detected, forcing re-run")
            return True

        if not last_update_date:
            return True

        days_since_update = (d - last_update_date).days
        if days_since_update >= 7:
            logger.info(f"[MacroAnalyzer] {days_since_update} days since last update, running weekly update")
            return True

        logger.info(f"[MacroAnalyzer] skipping update ({days_since_update} days since last)")
        return False


# =========================================================================
# Helper Functions
# =========================================================================

def _dim_name_cn(name: str) -> str:
    """Map dimension name to Chinese."""
    mapping = {
        "liquidity_environment": "流动性环境",
        "economic_cycle_position": "经济周期位置",
        "inflation_and_cost": "通胀与成本",
        "policy_direction": "政策方向",
        "global_linkage": "全球联动",
    }
    return mapping.get(name, name)
