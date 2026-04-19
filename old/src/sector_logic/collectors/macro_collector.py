# -*- coding: utf-8 -*-
"""
MacroCollector: fetches macro environment data for China + US + global.

Phase 2.5 Enhanced:
- China: M0/M1/M2, full-term Shibor, Hibor, social financing stock,
  PMI detailed sub-indicators (50+ fields), CPI/PPI detailed breakdowns
- Derived indicators: M1-M2 scissors, PPI-CPI scissors, Shibor term structure,
  social financing YoY, PMI leading index, Shibor-Hibor spread
- Time series: 12-month rolling window, trend detection, inflection points, momentum
- Economic cycle: four-quadrant classification (recovery/overheating/stagflation/recession)
- Leading signals: early warning based on derived indicators + trend combination

Sources:
  China:
  - Tushare: cn_m, shibor, hibor, sf_month, cn_pmi, cn_cpi, cn_ppi
  - 央行官网: DR007, MLF/SLF 利率 (Phase 2 已有)

  US:
  - Tushare: us_treasury, economic indicators
  - Fed 官网: FOMC 决策

  Global:
  - Polymarket: 预测市场概率
  - 新闻：地缘政治风险

Priority:
  - Priority 0: Tushare/AKShare (structured API)
  - Priority 1: 央行/Fed 官网 (semi-structured)
  - Priority 2: Polymarket (supplementary)
  - Fallback: cached data from DataStore
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import AsyncCollector

logger = logging.getLogger(__name__)

# Minimum months required for meaningful trend analysis
MIN_TREND_WINDOW = 6
DEFAULT_TREND_WINDOW = 12

# Consecutive months for trend direction detection
CONSECUTIVE_DIR_MONTHS = 3

# Threshold for trend direction change (5% of absolute value)
TREND_THRESHOLD = 0.05

# Inflection point significance filter (10% change)
INFLECTION_MIN_CHANGE = 0.10

# Inflection point lookback limit (months)
INFLECTION_LOOKBACK = 24


class MacroCollector(AsyncCollector):
    """
    Collects macro environment data for China + US + global.

    Phase 2.5 enhanced with derived indicators, trend analysis,
    and economic cycle four-quadrant classification.
    """

    def __init__(self, datastore, skill_loader=None):
        super().__init__(datastore, max_retries=3, base_delay=1.0, fallback_enabled=True)
        self.skill_loader = skill_loader
        self._trend_config = None
        self._load_trend_config()

    def _load_trend_config(self):
        """Load trend analysis config from skill file if available."""
        if self.skill_loader:
            try:
                config = self.skill_loader.load_macro_config("trend-analysis-config.json")
                if config:
                    self._trend_config = config
                    return
            except Exception:
                pass

        # Built-in defaults
        self._trend_config = {
            "rolling_window": {"default_length": 12, "minimum_length": 6},
            "trend_detection": {
                "consecutive_months": 3,
                "threshold": 0.05,
            },
            "momentum_calculation": {
                "short_term": 3,
                "medium_term": 6,
                "long_term": 12,
            },
            "inflection_point_detection": {
                "min_change_magnitude": 0.10,
                "lookback_limit": 24,
            },
        }

    async def fetch_data(self, target: str, d: date) -> Optional[Dict[str, Any]]:
        """
        Fetch macro data snapshot.

        Returns enriched snapshot with Phase 2.5 fields:
        - derived_indicators: M1-M2 scissors, PPI-CPI scissors, etc.
        - trend_analysis: 12-month trends for key indicators
        - cycle_position: economic cycle four-quadrant classification
        - leading_signals: early warning signals
        """
        logger.info(f"[MacroCollector] fetching macro data for {d.isoformat()}")

        # 1. China macro data (Phase 2.5 enhanced)
        china_data = await self._fetch_china_data_enhanced(d)

        # 2. US macro data
        us_data = await self._fetch_us_data(d)

        # 3. Global/Polymarket data
        global_data = await self._fetch_global_data(d)

        # 4. Calculate derived indicators (pure math)
        derived_indicators = self._calculate_derived_indicators(china_data, us_data)

        # 5. Load 12-month history
        historical_data = await self._load_12m_history(d)

        # 6. Calculate trend analysis
        trend_analysis = self._calculate_trend_analysis(historical_data, derived_indicators)

        # 7. Calculate cycle position
        cycle_position = self._calculate_cycle_position(derived_indicators, trend_analysis)

        # 8. Generate leading signals
        leading_signals = self._generate_leading_signals(derived_indicators, trend_analysis)

        # Aggregate into unified snapshot
        snapshot = {
            "snapshot_date": d.isoformat(),
            "china": china_data,
            "us": us_data,
            "global": global_data,
            "derived_indicators": derived_indicators,
            "trend_analysis": trend_analysis,
            "cycle_position": cycle_position,
            "leading_signals": leading_signals,
        }

        # Compute preliminary scores (final scoring done by MacroAnalyzer)
        snapshot["china_score"] = self._calc_china_score(china_data, derived_indicators)
        snapshot["us_score"] = self._calc_us_score(us_data)
        snapshot["global_score"] = self._calc_global_score(global_data)

        logger.info(
            f"[MacroCollector] macro snapshot: "
            f"china={snapshot['china_score']:.1f}, us={snapshot['us_score']:.1f}, "
            f"global={snapshot['global_score']:.1f}, "
            f"cycle={cycle_position.get('quadrant', 'unknown')}"
        )
        return snapshot

    # =========================================================================
    # China Data Collection (Phase 2.5 Enhanced)
    # =========================================================================

    async def _fetch_china_data_enhanced(self, d: date) -> Dict[str, Any]:
        """
        Fetch China macro data with Phase 2.5 enhancements.

        Includes: M0/M1/M2, full-term Shibor, Hibor, social financing stock,
        PMI detailed sub-indicators, CPI/PPI detailed breakdowns.
        """
        data: Dict[str, Any] = {
            # Money supply (monthly, ~15 day lag)
            "m0": None,
            "m1": None,
            "m2": None,
            "m0_yoy": None,
            "m1_yoy": None,
            "m2_yoy": None,
            # Interest rates (daily)
            "dr007": None,
            "mlf_rate": None,
            # Shibor full term structure (daily)
            "shibor_overnight": None,
            "shibor_1w": None,
            "shibor_2w": None,
            "shibor_1m": None,
            "shibor_3m": None,
            "shibor_6m": None,
            "shibor_9m": None,
            "shibor_1y": None,
            # Hibor (daily, cross-border liquidity)
            "hibor_overnight": None,
            "hibor_3m": None,
            "hibor_1y": None,
            # Social financing (monthly)
            "social_financing_stock": None,
            "social_financing_inc_month": None,
            # PMI detailed (monthly, 50+ fields, key ones below)
            "pmi": None,
            "pmi_production": None,
            "pmi_new_orders": None,
            "pmi_inventory": None,
            "pmi_employment": None,
            "pmi_new_export_orders": None,
            "pmi_purchase_price": None,
            "pmi_ex_factory_price": None,
            # CPI detailed (monthly)
            "cpi_yoy": None,
            "cpi_mom": None,
            "cpi_town_yoy": None,
            "cpi_country_yoy": None,
            # PPI detailed (monthly)
            "ppi_yoy": None,
            "ppi_mom": None,
            "ppi_mp_yoy": None,  # 生产资料 (means of production)
            "ppi_cg_yoy": None,  # 生活资料 (consumer goods)
        }

        try:
            import tushare as ts
            from src.config import get_config

            config = get_config()
            tushare_token = config.tushare_token if hasattr(config, "tushare_token") else None

            if not tushare_token:
                logger.warning("[MacroCollector] tushare_token not configured, China data will be incomplete")
                return data

            pro = ts.pro_api(tushare_token)

            # --- M0/M1/M2 ---
            try:
                search_end = d.replace(day=1) if d.day > 15 else d
                if search_end.month > 2:
                    search_start = search_end.replace(month=search_end.month - 3)
                else:
                    search_start = search_end.replace(year=search_end.year - 1, month=search_end.month + 9)

                cn_m_df = pro.cn_m(
                    start_m=search_start.strftime("%Y%m"),
                    end_m=search_end.strftime("%Y%m"),
                )
                if cn_m_df is not None and not cn_m_df.empty:
                    latest = cn_m_df.iloc[-1]
                    data["m0"] = float(latest.get("m0", 0)) if latest.get("m0") else None
                    data["m1"] = float(latest.get("m1", 0)) if latest.get("m1") else None
                    data["m2"] = float(latest.get("m2", 0)) if latest.get("m2") else None
                    data["m0_yoy"] = float(latest.get("m0_yoy", 0)) if latest.get("m0_yoy") else None
                    data["m1_yoy"] = float(latest.get("m1_yoy", 0)) if latest.get("m1_yoy") else None
                    data["m2_yoy"] = float(latest.get("m2_yoy", 0)) if latest.get("m2_yoy") else None
                    logger.debug(
                        f"[MacroCollector] M1/M2: m1_yoy={data['m1_yoy']}%, m2_yoy={data['m2_yoy']}%"
                    )
            except Exception as e:
                logger.warning(f"[MacroCollector] cn_m fetch failed: {e}")

            # --- Shibor full term structure ---
            try:
                shibor_df = pro.shibor(
                    start_date=d.strftime("%Y%m%d"),
                    end_date=d.strftime("%Y%m%d"),
                )
                if shibor_df is not None and not shibor_df.empty:
                    latest = shibor_df.iloc[0]
                    data["shibor_overnight"] = _safe_float(latest.get("on"))
                    data["shibor_1w"] = _safe_float(latest.get("1w"))
                    data["shibor_2w"] = _safe_float(latest.get("2w"))
                    data["shibor_1m"] = _safe_float(latest.get("1m"))
                    data["shibor_3m"] = _safe_float(latest.get("3m"))
                    data["shibor_6m"] = _safe_float(latest.get("6m"))
                    data["shibor_9m"] = _safe_float(latest.get("9m"))
                    data["shibor_1y"] = _safe_float(latest.get("1y"))
            except Exception as e:
                logger.warning(f"[MacroCollector] shibor fetch failed: {e}")

            # --- Hibor ---
            try:
                hibor_df = pro.hibor(
                    start_date=d.strftime("%Y%m%d"),
                    end_date=d.strftime("%Y%m%d"),
                )
                if hibor_df is not None and not hibor_df.empty:
                    latest = hibor_df.iloc[0]
                    data["hibor_overnight"] = _safe_float(latest.get("on"))
                    data["hibor_3m"] = _safe_float(latest.get("3m"))
                    data["hibor_1y"] = _safe_float(latest.get("12m"))
            except Exception as e:
                logger.warning(f"[MacroCollector] hibor fetch failed: {e}")

            # --- Social financing stock ---
            try:
                search_end = d.replace(day=1) if d.day > 15 else d
                if search_end.month > 3:
                    search_start = search_end.replace(month=search_end.month - 3)
                else:
                    search_start = search_end.replace(year=search_end.year - 1, month=search_end.month + 9)

                sf_df = pro.sf_month(
                    start_m=search_start.strftime("%Y%m"),
                    end_m=search_end.strftime("%Y%m"),
                )
                if sf_df is not None and not sf_df.empty:
                    latest = sf_df.iloc[-1]
                    data["social_financing_stock"] = _safe_float(latest.get("stk_endval"))
                    data["social_financing_inc_month"] = _safe_float(latest.get("inc_month"))
            except Exception as e:
                logger.warning(f"[MacroCollector] sf_month fetch failed: {e}")

            # --- PMI detailed sub-indicators ---
            try:
                search_end = d.replace(day=1) if d.day > 15 else d
                if search_end.month > 2:
                    search_start = search_end.replace(month=search_end.month - 3)
                else:
                    search_start = search_end.replace(year=search_end.year - 1, month=search_end.month + 9)

                pmi_fields = (
                    "month,pmi010000,pmi010400,pmi010500,pmi010700,"
                    "pmi010800,pmi010900,pmi011200,pmi011300"
                )
                pmi_df = pro.cn_pmi(
                    start_m=search_start.strftime("%Y%m"),
                    end_m=search_end.strftime("%Y%m"),
                    fields=pmi_fields,
                )
                if pmi_df is not None and not pmi_df.empty:
                    latest = pmi_df.iloc[-1]
                    data["pmi"] = _safe_float(latest.get("pmi010000"))
                    data["pmi_production"] = _safe_float(latest.get("pmi010400"))
                    data["pmi_new_orders"] = _safe_float(latest.get("pmi010500"))
                    data["pmi_inventory"] = _safe_float(latest.get("pmi010700"))
                    data["pmi_employment"] = _safe_float(latest.get("pmi010800"))
                    data["pmi_new_export_orders"] = _safe_float(latest.get("pmi010900"))
                    data["pmi_purchase_price"] = _safe_float(latest.get("pmi011200"))
                    data["pmi_ex_factory_price"] = _safe_float(latest.get("pmi011300"))
            except Exception as e:
                logger.warning(f"[MacroCollector] cn_pmi fetch failed: {e}")

            # --- CPI detailed breakdown ---
            try:
                search_end = d.replace(day=1) if d.day > 15 else d
                if search_end.month > 2:
                    search_start = search_end.replace(month=search_end.month - 3)
                else:
                    search_start = search_end.replace(year=search_end.year - 1, month=search_end.month + 9)

                cpi_df = pro.cn_cpi(
                    start_m=search_start.strftime("%Y%m"),
                    end_m=search_end.strftime("%Y%m"),
                )
                if cpi_df is not None and not cpi_df.empty:
                    latest = cpi_df.iloc[-1]
                    data["cpi_yoy"] = _safe_float(latest.get("nt_yoy"))
                    data["cpi_mom"] = _safe_float(latest.get("nt_mom"))
                    data["cpi_town_yoy"] = _safe_float(latest.get("town_yoy"))
                    data["cpi_country_yoy"] = _safe_float(latest.get("cnt_yoy"))
            except Exception as e:
                logger.warning(f"[MacroCollector] cn_cpi fetch failed: {e}")

            # --- PPI detailed breakdown ---
            try:
                search_end = d.replace(day=1) if d.day > 15 else d
                if search_end.month > 2:
                    search_start = search_end.replace(month=search_end.month - 3)
                else:
                    search_start = search_end.replace(year=search_end.year - 1, month=search_end.month + 9)

                ppi_df = pro.cn_ppi(
                    start_m=search_start.strftime("%Y%m"),
                    end_m=search_end.strftime("%Y%m"),
                )
                if ppi_df is not None and not ppi_df.empty:
                    latest = ppi_df.iloc[-1]
                    data["ppi_yoy"] = _safe_float(latest.get("ppi_yoy"))
                    data["ppi_mom"] = _safe_float(latest.get("ppi_mom"))
                    data["ppi_mp_yoy"] = _safe_float(latest.get("ppi_mp_yoy"))
                    data["ppi_cg_yoy"] = _safe_float(latest.get("ppi_cg_yoy"))
            except Exception as e:
                logger.warning(f"[MacroCollector] cn_ppi fetch failed: {e}")

        except Exception as e:
            logger.error(f"[MacroCollector] China data fetch error: {e}")

        return data

    # =========================================================================
    # US & Global Data (unchanged from Phase 2, minor cleanup)
    # =========================================================================

    async def _fetch_us_data(self, d: date) -> Dict[str, Any]:
        """Fetch US macro data."""
        data: Dict[str, Any] = {
            "fed_funds_rate": None,
            "treasury_10y": None,
            "ism_pmi": None,
            "nonfarm_payrolls": None,
            "unemployment_rate": None,
        }

        try:
            import tushare as ts
            from src.config import get_config

            config = get_config()
            tushare_token = config.tushare_token if hasattr(config, "tushare_token") else None

            if tushare_token:
                pro = ts.pro_api(tushare_token)

                # US Treasury yields
                try:
                    us_data = pro.us_treasury()
                    if us_data is not None and not us_data.empty:
                        data["treasury_10y"] = _safe_float(us_data.get("tc_10y"))
                except Exception as e:
                    logger.warning(f"[MacroCollector] US Treasury fetch failed: {e}")

        except Exception as e:
            logger.error(f"[MacroCollector] US data fetch error: {e}")

        data["signal_source"] = "tushare_fallback"
        return data

    async def _fetch_global_data(self, d: date) -> Dict[str, Any]:
        """Fetch global/Polymarket data."""
        data: Dict[str, Any] = {
            "polymarket": {},
            "geopolitical_risk": "normal",
            "tariff_risk": "normal",
        }

        # Polymarket data collection (deferred to PolymarketCollector)
        data["signal_source"] = "placeholder"
        return data

    # =========================================================================
    # Derived Indicators (Phase 2.5 — pure math, zero LLM)
    # =========================================================================

    def _calculate_derived_indicators(
        self, china: Dict, us: Dict
    ) -> Dict[str, Any]:
        """
        Calculate Phase 2.5 derived indicators from raw macro data.

        All calculations are pure math — no LLM calls.
        Returns dict with derived indicator values and metadata.
        """
        derived: Dict[str, Any] = {}

        # M1-M2 剪刀差 (leading 3-6 months)
        if china.get("m1_yoy") is not None and china.get("m2_yoy") is not None:
            value = china["m1_yoy"] - china["m2_yoy"]
            derived["m1_m2_scissors"] = {
                "current": round(value, 2),
                "prev_month": None,  # filled from historical data
                "prev_quarter": None,
                "trend": None,  # filled from trend analysis
                "interpretation": _interpret_m1_m2(value),
            }

        # PPI-CPI 剪刀差 (coincident, enterprise profit pressure)
        if china.get("ppi_yoy") is not None and china.get("cpi_yoy") is not None:
            value = china["ppi_yoy"] - china["cpi_yoy"]
            derived["ppi_cpi_scissors"] = {
                "current": round(value, 2),
                "prev_month": None,
                "prev_quarter": None,
                "trend": None,
                "interpretation": _interpret_ppi_cpi(value),
            }

        # Shibor 期限结构斜率 (coincident, liquidity expectation)
        if china.get("shibor_1y") is not None and china.get("shibor_overnight") is not None:
            slope = (china["shibor_1y"] - china["shibor_overnight"]) / 365
            derived["shibor_term_structure"] = {
                "slope": round(slope, 6),
                "prev_month": None,
                "interpretation": _interpret_shibor_slope(slope),
            }

        # Shibor-Hibor 利差 (coincident, cross-border capital flow)
        if china.get("shibor_overnight") is not None and china.get("hibor_overnight") is not None:
            spread = china["shibor_overnight"] - china["hibor_overnight"]
            derived["shibor_hibor_spread"] = {
                "current": round(spread, 4),
                "prev_month": None,
                "interpretation": _interpret_shibor_hibor(spread),
            }

        # PMI 领先指数 (leading 2-3 months)
        if china.get("pmi_new_orders") is not None and china.get("pmi_inventory") is not None:
            value = china["pmi_new_orders"] - china["pmi_inventory"]
            derived["pmi_leading_index"] = {
                "current": round(value, 2),
                "prev_month": None,
                "prev_quarter": None,
                "trend": None,
                "interpretation": _interpret_pmi_leading(value),
            }

        # 社融存量增速 (leading 2-4 months)
        if china.get("social_financing_stock") is not None:
            sf_stock = china["social_financing_stock"]
            # Calculate YoY if we have last year's data
            # This will be enhanced when historical data is loaded
            derived["social_financing_growth"] = {
                "stock_yoy": None,  # calculated in _load_12m_history
                "stock_current": sf_stock,
                "prev_month": None,
                "prev_quarter": None,
                "trend": None,
                "interpretation": "社融存量增速待计算（需要去年同期数据）",
            }

        return derived

    # =========================================================================
    # 12-Month History & Trend Analysis
    # =========================================================================

    async def _load_12m_history(self, d: date) -> List[Dict]:
        """
        Load past 12 months of macro snapshots from DataStore.

        Returns list of historical snapshots sorted by date ascending.
        """
        historical = []
        for months_back in range(1, DEFAULT_TREND_WINDOW + 1):
            # Go to the 15th of each month for consistency (monthly data mid-month)
            target_month = d.month - months_back
            target_year = d.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1

            # Use 15th of the month as snapshot date
            try:
                hist_date = date(target_year, target_month, 15)
            except ValueError:
                continue

            snapshot = self.datastore.get_snapshot(hist_date, "macro")
            if snapshot and snapshot.get("derived_indicators"):
                historical.append(snapshot)

        # Sort by date ascending
        historical.sort(key=lambda x: x.get("snapshot_date", ""))
        return historical

    def _calculate_trend_analysis(
        self,
        historical: List[Dict],
        current_derived: Dict,
    ) -> Dict[str, Any]:
        """
        Calculate trend analysis for key derived indicators.

        Method: consecutive direction change over 3+ months.
        Returns dict of {indicator_name: {trend, momentum, inflection_point, rolling_12m_data, confidence}}.
        """
        key_indicators = [
            "m1_m2_scissors",
            "ppi_cpi_scissors",
            "shibor_term_structure",
            "pmi_leading_index",
        ]

        trend_config = self._trend_config.get("trend_detection", {})
        consecutive_months = trend_config.get("consecutive_months", 3)
        threshold = trend_config.get("threshold", 0.05)

        momentum_config = self._trend_config.get("momentum_calculation", {})
        short_term = momentum_config.get("short_term", 3)

        inflection_config = self._trend_config.get("inflection_point_detection", {})
        min_change = inflection_config.get("min_change_magnitude", 0.10)
        lookback = inflection_config.get("lookback_limit", 24)

        result: Dict[str, Any] = {}

        for indicator in key_indicators:
            # Collect historical values for this indicator
            values = []
            for snap in historical:
                derived = snap.get("derived_indicators", {})
                ind = derived.get(indicator, {})
                val = ind.get("current") or ind.get("slope")
                if val is not None:
                    values.append({"date": snap.get("snapshot_date"), "value": val})

            # Add current value
            current_val = None
            if indicator == "shibor_term_structure":
                current_val = current_derived.get(indicator, {}).get("slope")
            else:
                current_val = current_derived.get(indicator, {}).get("current")
            if current_val is not None:
                from datetime import date as date_cls
                values.append({"date": date_cls.today().isoformat(), "value": current_val})

            if len(values) < consecutive_months:
                result[indicator] = {
                    "trend": "insufficient_data",
                    "momentum": 0.0,
                    "inflection_point": None,
                    "rolling_12m_data": [v["value"] for v in values],
                    "confidence": "low",
                }
                continue

            # Extract values array
            vals = [v["value"] for v in values]
            dates = [v["date"] for v in values]

            # Trend: consecutive direction change
            trend = _detect_trend(vals, consecutive_months, threshold)

            # Momentum: (current - N_periods_ago) / |N_periods_ago|
            n = min(short_term, len(vals) - 1)
            momentum = 0.0
            if n > 0 and vals[-(n + 1)] != 0:
                momentum = (vals[-1] - vals[-(n + 1)]) / abs(vals[-(n + 1)])

            # Inflection point: direction reversal
            inflection_point = _detect_inflection(vals, dates, min_change, lookback)

            confidence = "high" if len(vals) >= 12 else ("medium" if len(vals) >= 8 else "low")

            result[indicator] = {
                "trend": trend,
                "momentum": round(momentum, 4),
                "inflection_point": inflection_point,
                "rolling_12m_data": vals[-12:] if len(vals) >= 12 else vals,
                "confidence": confidence,
            }

        return result

    # =========================================================================
    # Economic Cycle Four-Quadrant Classification
    # =========================================================================

    def _calculate_cycle_position(
        self, derived: Dict, trend_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Classify economic cycle position into four quadrants.

        Growth momentum = f(PMI leading index, social financing growth)
        Liquidity momentum = f(M1-M2 scissors, Shibor term structure)

        Quadrants:
        - 复苏期: growth↑ + liquidity↑
        - 过热期: growth↑ + liquidity↓
        - 滞胀期: growth↓ + liquidity↓
        - 衰退期: growth↓ + liquidity↑
        """
        growth_momentum = 0.0
        liquidity_momentum = 0.0

        # Growth: PMI leading index (normalized to -1~1 by dividing by 10)
        pmi_leading = derived.get("pmi_leading_index", {}).get("current")
        if pmi_leading is not None:
            growth_momentum += pmi_leading / 10.0

        # Growth: trend momentum from PMI leading index
        pmi_trend = trend_analysis.get("pmi_leading_index", {})
        pmi_trend_momentum = pmi_trend.get("momentum", 0)
        growth_momentum += pmi_trend_momentum * 0.3  # weight for trend

        # Liquidity: M1-M2 scissors (normalized to -1~1 by dividing by 10)
        m1m2 = derived.get("m1_m2_scissors", {}).get("current")
        if m1m2 is not None:
            liquidity_momentum += m1m2 / 10.0

        # Liquidity: Shibor term structure trend momentum
        shibor_trend = trend_analysis.get("shibor_term_structure", {})
        shibor_momentum = shibor_trend.get("momentum", 0)
        liquidity_momentum += shibor_momentum * 0.3

        # Clamp to -1~1
        growth_momentum = max(-1.0, min(1.0, growth_momentum))
        liquidity_momentum = max(-1.0, min(1.0, liquidity_momentum))

        # Quadrant classification
        if growth_momentum > 0 and liquidity_momentum > 0:
            quadrant = "复苏期"
        elif growth_momentum > 0 and liquidity_momentum <= 0:
            quadrant = "过热期"
        elif growth_momentum <= 0 and liquidity_momentum <= 0:
            quadrant = "滞胀期"
        else:  # growth <= 0 and liquidity > 0
            quadrant = "衰退期"

        return {
            "growth_momentum": round(growth_momentum, 2),
            "liquidity_momentum": round(liquidity_momentum, 2),
            "quadrant": quadrant,
        }

    # =========================================================================
    # Leading Signals
    # =========================================================================

    def _generate_leading_signals(
        self, derived: Dict, trend_analysis: Dict
    ) -> List[Dict]:
        """
        Generate leading signal warnings based on derived indicators + trends.

        Returns list of signal dicts, empty if no signals detected.
        """
        signals: List[Dict] = []

        # M1-M2 剪刀差 narrowing warning
        m1m2 = derived.get("m1_m2_scissors", {})
        m1m2_trend = trend_analysis.get("m1_m2_scissors", {})
        if (
            m1m2.get("current") is not None
            and m1m2_trend.get("trend") == "declining"
            and m1m2_trend.get("momentum", 0) < -0.1
        ):
            signals.append({
                "indicator": "M1-M2 剪刀差",
                "current_value": m1m2["current"],
                "trend": "收窄",
                "duration_months": 3,
                "prediction": "预示 2-3 月后流动性收紧",
                "confidence": 0.75,
            })

        # PMI 领先指数 expansion warning
        pmi_leading = derived.get("pmi_leading_index", {})
        pmi_trend = trend_analysis.get("pmi_leading_index", {})
        if (
            pmi_leading.get("current") is not None
            and pmi_leading["current"] > 2.0
            and pmi_trend.get("trend") == "increasing"
        ):
            signals.append({
                "indicator": "PMI 新订单-库存差",
                "current_value": pmi_leading["current"],
                "trend": "扩张",
                "duration_months": 2,
                "prediction": "经济处于主动补库存阶段，持续 3-4 月",
                "confidence": 0.68,
            })

        # Shibor-Hibor spread widening warning
        shibor_hibor = derived.get("shibor_hibor_spread", {})
        if shibor_hibor.get("current") is not None and shibor_hibor["current"] > 0.5:
            signals.append({
                "indicator": "Shibor-Hibor 利差",
                "current_value": shibor_hibor["current"],
                "trend": "扩大",
                "duration_months": 1,
                "prediction": "跨境资金流出压力增加",
                "confidence": 0.60,
            })

        # PPI-CPI 剪刀差 expansion warning (cost pressure)
        ppi_cpi = derived.get("ppi_cpi_scissors", {})
        ppi_cpi_trend = trend_analysis.get("ppi_cpi_scissors", {})
        if (
            ppi_cpi.get("current") is not None
            and ppi_cpi["current"] > 3.0
            and ppi_cpi_trend.get("trend") == "increasing"
        ):
            signals.append({
                "indicator": "PPI-CPI 剪刀差",
                "current_value": ppi_cpi["current"],
                "trend": "扩大",
                "duration_months": 2,
                "prediction": "中下游企业利润承压加剧",
                "confidence": 0.70,
            })

        return signals

    # =========================================================================
    # Scoring (preliminary, final scoring done by MacroAnalyzer)
    # =========================================================================

    def _calc_china_score(
        self, china_data: Dict, derived_indicators: Dict
    ) -> float:
        """Calculate China macro score (0-10) with Phase 2.5 derived indicators."""
        score = 5.0

        # Liquidity: M1-M2 scissors
        m1m2 = derived_indicators.get("m1_m2_scissors", {}).get("current")
        if m1m2 is not None:
            if m1m2 > 2.0:
                score += 2.0  # very loose
            elif m1m2 > 0.5:
                score += 1.0  # loose
            elif m1m2 < -2.0:
                score -= 1.5  # very tight
            elif m1m2 < -0.5:
                score -= 0.5  # tight

        # Shibor overnight
        shibor = china_data.get("shibor_overnight")
        if shibor:
            if shibor < 1.8:
                score += 1.0
            elif shibor > 2.5:
                score -= 1.0

        # PMI (economic activity)
        pmi = china_data.get("pmi")
        if pmi is not None:
            if pmi > 51:
                score += 1.0
            elif pmi > 50:
                score += 0.5
            elif pmi < 49:
                score -= 1.0

        return max(0.0, min(10.0, score))

    def _calc_us_score(self, us_data: Dict) -> float:
        """Calculate US macro score (0-10)."""
        score = 5.0

        treasury_10y = us_data.get("treasury_10y")
        if treasury_10y:
            if treasury_10y < 3.5:
                score += 1.5
            elif treasury_10y > 5.0:
                score -= 1.5
            elif treasury_10y > 4.5:
                score -= 0.5

        fed_rate = us_data.get("fed_funds_rate")
        if fed_rate:
            if fed_rate > 5.5:
                score -= 1.0
            elif fed_rate < 3.0:
                score += 1.0

        return max(0.0, min(10.0, score))

    def _calc_global_score(self, global_data: Dict) -> float:
        """Calculate global macro score (0-10)."""
        score = 5.0

        geo_risk = global_data.get("geopolitical_risk", "normal")
        if geo_risk == "elevated":
            score -= 1.5
        elif geo_risk == "severe":
            score -= 3.0

        tariff_risk = global_data.get("tariff_risk", "normal")
        if tariff_risk == "elevated":
            score -= 1.0
        elif tariff_risk == "severe":
            score -= 2.0

        return max(0.0, min(10.0, score))

    # =========================================================================
    # Interface
    # =========================================================================

    def get_phase05_macro_inputs(self, d: date = None) -> Dict[str, Any]:
        """
        Extract Phase 0.5 L0 inputs from existing macro data.

        Returns:
            {
                pmi: float or None,
                m1_m2_diff: float or None,  # M1-M2 剪刀差
                shibor_trend: str,  # 'up' / 'down' / 'neutral'
                policy_easing: bool,
                liquidity_tightening: bool,
                data_available: bool,
            }
        """
        from datetime import date as _date
        if d is None:
            d = _date.today()

        # Get latest macro snapshot
        dates = self.list_available_dates("macro")
        if not dates:
            return {"data_available": False}

        # Find closest date
        target_date = min(dates, key=lambda x: abs((x - d).days))
        snapshot = self.get_snapshot(target_date, "macro")
        if not snapshot:
            return {"data_available": False}

        china = snapshot.get("china", {})
        derived = snapshot.get("derived_indicators", {})
        trend = snapshot.get("trend_analysis", {})

        # PMI
        pmi = china.get("pmi")
        if pmi is None:
            pmi = china.get("pmi_new_orders")

        # M1-M2 剪刀差
        m1m2 = derived.get("m1_m2_scissors", {}).get("current")
        if m1m2 is None:
            m1 = china.get("m1_yoy")
            m2 = china.get("m2_yoy")
            if m1 is not None and m2 is not None:
                m1m2 = m1 - m2

        # Shibor trend
        shibor_trend_data = trend.get("shibor_term_structure", {})
        shibor_trend = shibor_trend_data.get("trend", "neutral")
        if shibor_trend == "increasing":
            shibor_trend = "up"
        elif shibor_trend == "decreasing":
            shibor_trend = "down"
        else:
            shibor_trend = "neutral"

        # Policy easing detection (check if MLF/DR007 rate decreased recently)
        policy_easing = False
        mlf_rate = china.get("mlf_rate")
        if mlf_rate:
            # Check recent trend: if MLF rate decreased recently
            mlf_trend = trend.get("mlf_rate", {}).get("trend", "stable")
            if mlf_trend == "decreasing":
                policy_easing = True

        # Liquidity tightening detection
        liquidity_tightening = False
        shibor_on = china.get("shibor_overnight")
        if shibor_on and shibor_trend == "up":
            if shibor_on > 2.5:
                liquidity_tightening = True

        return {
            "pmi": pmi,
            "m1_m2_diff": m1m2,
            "shibor_trend": shibor_trend,
            "policy_easing": policy_easing,
            "liquidity_tightening": liquidity_tightening,
            "data_available": True,
            "snapshot_date": target_date.isoformat(),
        }

    def get_targets(self, d: date) -> List[str]:
        """Return list of targets (always ["macro"])."""
        return ["macro"]

    async def collect(self, d: date) -> Optional[Dict[str, Any]]:
        """Convenience method: fetch macro data and return."""
        return await self.fetch_with_retry("macro", d)


# =========================================================================
# Helper Functions
# =========================================================================

def _safe_float(value) -> Optional[float]:
    """Safely convert to float, returning None on failure."""
    if value is None:
        return None
    try:
        v = float(value)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None


def _interpret_m1_m2(value: float) -> str:
    """Interpret M1-M2 scissors value."""
    if value > 2.0:
        return "M1 增速显著高于 M2，流动性非常宽松，股市受益"
    elif value > 0.5:
        return "M1 增速高于 M2，流动性宽松，企业活期存款增加"
    elif value > -0.5:
        return "M1 与 M2 增速接近，流动性中性"
    elif value > -2.0:
        return "M1 增速低于 M2，流动性偏紧，企业活期存款减少"
    else:
        return "M1 增速显著低于 M2，流动性收紧，股市承压"


def _interpret_ppi_cpi(value: float) -> str:
    """Interpret PPI-CPI scissors value."""
    if value > 3.0:
        return "上游成本压力显著向下游传导，中下游企业利润承压"
    elif value > 1.0:
        return "上游成本压力向下游传导，中下游企业利润承压"
    elif value > -1.0:
        return "成本传导平衡，企业利润稳定"
    else:
        return "上游成本压力小于下游价格，企业利润改善"


def _interpret_shibor_slope(slope: float) -> str:
    """Interpret Shibor term structure slope."""
    if slope > 0.008:
        return "期限利差陡峭，长期流动性宽松预期"
    elif slope > 0.005:
        return "期限利差正常"
    elif slope > 0.002:
        return "期限利差趋平，短期流动性偏紧预期"
    else:
        return "期限利差倒挂，流动性极度紧张，经济衰退信号"


def _interpret_shibor_hibor(spread: float) -> str:
    """Interpret Shibor-Hibor spread."""
    if spread > 0.5:
        return "利差显著扩大，跨境资金流出压力"
    elif spread > 0.2:
        return "利差偏大，跨境资金流出压力"
    elif spread > -0.1:
        return "利差正常，跨境资金流动平衡"
    else:
        return "利差收窄或倒挂，跨境资金流入，人民币流动性宽松"


def _interpret_pmi_leading(value: float) -> str:
    """Interpret PMI leading index."""
    if value > 3.0:
        return "新订单显著高于库存，主动补库存，经济扩张"
    elif value > 1.0:
        return "新订单高于库存，经济温和扩张"
    elif value > -1.0:
        return "新订单与库存接近，经济平稳"
    else:
        return "新订单低于库存，经济收缩，去库存阶段"


def _detect_trend(values: List[float], consecutive_months: int, threshold: float) -> str:
    """
    Detect trend using consecutive direction change method.

    Returns: "increasing" | "declining" | "stable"
    """
    if len(values) < consecutive_months:
        return "insufficient_data"

    recent = values[-consecutive_months:]
    diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]

    if not diffs:
        return "stable"

    # Check if all diffs are positive and cumulative change exceeds threshold
    abs_first = abs(values[-consecutive_months]) if values[-consecutive_months] != 0 else 1.0
    cumulative_change = (values[-1] - values[-consecutive_months]) / abs_first

    if all(d > threshold * abs_first / consecutive_months for d in diffs) and cumulative_change > threshold:
        return "increasing"
    elif all(d < -threshold * abs_first / consecutive_months for d in diffs) and cumulative_change < -threshold:
        return "declining"
    else:
        return "stable"


def _detect_inflection(
    values: List[float],
    dates: List[str],
    min_change: float,
    lookback: int,
) -> Optional[str]:
    """
    Detect inflection points (direction reversal).

    Returns the most recent inflection point date, or None.
    """
    limit = min(lookback, len(values) - 2)
    for i in range(len(values) - 2, len(values) - 2 - limit, -1):
        if i <= 0:
            break
        # Direction reversal: slope before vs after has opposite signs
        if (values[i] - values[i - 1]) * (values[i + 1] - values[i]) < 0:
            # Significance: inflection magnitude relative to the range
            swing = abs(values[i] - values[i - 1]) + abs(values[i + 1] - values[i])
            val_range = max(abs(v) for v in values[max(0, i-2):min(len(values), i+3)])
            if val_range == 0:
                val_range = 1.0
            if swing / val_range > min_change:
                return dates[i] if i < len(dates) else None
    return None
