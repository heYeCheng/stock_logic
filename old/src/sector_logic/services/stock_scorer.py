# -*- coding: utf-8 -*-
"""
StockScorer: L3 stock scoring for Phase 0.5.

Calculates logic score, market score, composite score, catalyst markers,
and stock status identification.
"""

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def sigmoid(x: float, k: float = 4.0) -> float:
    """Numerically stable sigmoid with configurable k."""
    if k * x >= 0:
        return 1.0 / (1.0 + math.exp(-k * x))
    else:
        exp_kx = math.exp(k * x)
        return exp_kx / (1.0 + exp_kx)


class StockScorer:
    """
    L3 Stock Scorer (Phase 0.5).

    Scores individual stocks based on logic exposure, market behavior,
    catalysts, and multi-sector affiliation.
    """

    def __init__(self, stock_mapper=None, anchor_loader=None):
        self.stock_mapper = stock_mapper
        self.anchor_loader = anchor_loader

    def calculate_logic_score(self, stock_code: str, sector_code: str,
                              active_logics: List[Dict[str, Any]],
                              business_description: str = "",
                              k: float = 4.0) -> float:
        """
        Calculate stock_logic_score via sigmoid mapping.

        raw_logic_score = Σ(exposure_i × logic_i.strength × direction_sign)
        stock_logic_score = sigmoid(raw_logic_score, k)
        """
        if not active_logics:
            return 0.5

        # Get logic_match_score
        if self.stock_mapper:
            logic_match_score = self.stock_mapper.get_logic_match_score(
                stock_code, sector_code, business_description
            )
        else:
            logic_match_score = 0.1  # Default if no mapper

        # Calculate exposure and raw score
        raw_logic_score = 0.0
        for logic in active_logics:
            direction_sign = 1 if logic.get('direction', 'positive') == 'positive' else -1
            logic_strength = logic.get('current_strength', logic.get('strength', 0.5))

            # Get affiliation strength from mapper or default
            if self.stock_mapper and hasattr(self.stock_mapper, 'get_affiliation_strength'):
                affiliation_strength = self.stock_mapper.get_affiliation_strength(
                    stock_code, logic.get('sector_code', sector_code)
                )
            else:
                affiliation_strength = 1.0

            exposure = affiliation_strength * logic_match_score
            raw_logic_score += exposure * logic_strength * direction_sign

        # Map to 0-1 via sigmoid
        stock_logic_score = sigmoid(raw_logic_score, k)
        return round(stock_logic_score, 4)

    def calculate_market_score(self, stock_data: Dict[str, Any],
                               sector_data: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate stock_market_score from technical and sentiment data.

        Technical: trend(30%) + vol(25%) + rel_sector_strength(25%) + ATR(20%)
        Sentiment: 涨停(50%) + turnover(50%)
        """
        # Technical sub-scores
        trend_score = self._calc_technical_trend(stock_data)
        vol_score = self._calc_technical_vol(stock_data)
        rel_strength = self._calc_relative_sector_strength(stock_data, sector_data)
        atr_score = self._calc_atr_score(stock_data)

        technical = 0.30 * trend_score + 0.25 * vol_score + 0.25 * rel_strength + 0.20 * atr_score

        # Sentiment sub-scores
        limit_score = self._calc_limit_score(stock_data)
        turnover_score = self._calc_turnover_score(stock_data)

        sentiment = 0.50 * limit_score + 0.50 * turnover_score

        # Composite → sigmoid
        market_raw = 0.5 * technical + 0.5 * sentiment
        market_score = sigmoid((market_raw - 5) / 2)

        return round(market_score, 4)

    def _calc_technical_trend(self, stock_data: Dict) -> float:
        """Trend score based on MA20/MA60 alignment."""
        close = stock_data.get('close')
        ma20 = stock_data.get('ma20')
        ma60 = stock_data.get('ma60')

        if close and ma20 and ma60 and ma20 != 0 and ma60 != 0:
            score = 5 + 2.5 * ((close - ma20) / ma20 / 0.1 + (ma20 - ma60) / ma60 / 0.1)
            return max(0, min(10, score))
        return 5.0

    def _calc_technical_vol(self, stock_data: Dict) -> float:
        """Volume score based on volume ratio."""
        vol5 = stock_data.get('vol_ma5')
        vol20 = stock_data.get('vol_ma20')

        if vol5 and vol20 and vol20 != 0:
            vol_ratio = vol5 / vol20
            return min(10, max(0, (vol_ratio - 0.8) * 10 / 0.7))
        return 5.0

    def _calc_relative_sector_strength(self, stock_data: Dict,
                                       sector_data: Optional[Dict] = None) -> float:
        """Relative strength vs sector."""
        stock_ret = stock_data.get('ret_10d', 0)
        sector_ret = sector_data.get('ret_10d', 0) if sector_data else 0

        if sector_ret != 0:
            rel = stock_ret / sector_ret
        else:
            rel = 1.0

        return min(10, max(0, 5 + 5 * (rel - 1) / 0.5))

    def _calc_atr_score(self, stock_data: Dict) -> float:
        """ATR-based volatility score."""
        atr = stock_data.get('atr')
        atr_ma = stock_data.get('atr_ma')

        if atr and atr_ma and atr_ma != 0:
            atr_ratio = atr / atr_ma
            if atr_ratio < 0.8:
                return 7.0  # Low volatility, good for entry
            elif atr_ratio < 1.2:
                return 5.0  # Normal
            else:
                return 3.0  # High volatility, risky
        return 5.0

    def _calc_limit_score(self, stock_data: Dict) -> float:
        """Score based on recent limit-up occurrences."""
        lu_count = stock_data.get('limit_up_count_5d', 0)
        if lu_count >= 2:
            return 10.0
        elif lu_count == 1:
            return 7.0
        return 0.0

    def _calc_turnover_score(self, stock_data: Dict) -> float:
        """Score based on turnover activity."""
        turn_ratio = stock_data.get('turnover_ratio', 1.0)
        return min(10, max(0, (turn_ratio - 0.8) * 10 / 0.7))

    def calculate_catalyst(self, stock_data: Dict[str, Any]) -> str:
        """
        Determine catalyst marker.

        强: 近3日有涨停 OR 近5日涨幅>20% AND 量比>1.5
        中: 龙虎榜机构净买入 OR 北向资金连续3日净买入
        无: otherwise
        """
        # Check 强 conditions
        if stock_data.get('limit_up_count_3d', 0) > 0:
            return '强'

        ret_5d = stock_data.get('ret_5d', 0)
        vol_ratio = stock_data.get('vol_ratio', 1.0)
        if ret_5d > 0.20 and vol_ratio > 1.5:
            return '强'

        # Check 中 conditions
        if stock_data.get('dragon_tiger_net_buy', 0) > 0:
            return '中'

        if stock_data.get('northbound_consecutive_buy_3d', False):
            return '中'

        return '无'

    def calculate_composite(self, stock_logic_score: float,
                            stock_market_score: float) -> float:
        """
        Calculate composite score.

        stock_composite_score = 0.50 × stock_logic_score + 0.50 × stock_market_score
        """
        composite = 0.50 * stock_logic_score + 0.50 * stock_market_score
        return round(composite, 4)

    def identify_stock_status(self, stock_data: Dict[str, Any],
                              sector_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Identify stock status: 龙头/中军/跟风 + 蓄力中军 flag.
        """
        is_dragon = False
        is_core = False

        # 龙头: 近10日涨幅板块前10% AND 近5日有涨停 AND logic_match_score≥0.7
        if (stock_data.get('ret_10d_percentile', 0) >= 0.90 and
                stock_data.get('limit_up_count_5d', 0) > 0 and
                stock_data.get('logic_match_score', 0) >= 0.7):
            is_dragon = True

        # 中军: 总市值板块前5 AND 近20日日均成交额板块前5
        if (stock_data.get('market_cap_rank', 999) <= 5 and
                stock_data.get('avg_turnover_20d_rank', 999) <= 5):
            is_core = True

        if is_dragon:
            status = '龙头'
        elif is_core:
            status = '中军'
        else:
            status = '跟风'

        # 蓄力中军: normal/overheated state + 中军 + stock_market_score<0.5
        is_xuli = False
        if is_core:
            market_state = sector_data.get('market_state', 'unknown') if sector_data else 'unknown'
            market_score = stock_data.get('stock_market_score', 0.5)
            if market_state in ('normal', 'overheated') and market_score < 0.5:
                is_xuli = True

        return {'status': status, 'is_xuli': is_xuli}
