# -*- coding: utf-8 -*-
"""
MarketLayer: L2 market perception layer for Phase 0.5.

Pure price/volume analysis — never reads L1 logic data.
"""

import logging
import math
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        exp_x = math.exp(x)
        return exp_x / (1.0 + exp_x)


class MarketLayer:
    """
    L2 Market Layer (Phase 0.5).

    Calculates market radar, state classification, and leading concentration.
    """

    def __init__(self, anchor_loader=None):
        self.anchor_loader = anchor_loader
        self._sentiment_history = {}  # sector_code -> [sentiment_scores]

    def calculate_technical_score(self, sector_stocks: List[Dict[str, Any]],
                                  market_ret_10d: float = 0.0) -> Dict[str, Any]:
        """
        Calculate technical score (0-10) for a sector.

        Args:
            sector_stocks: List of stock dicts with OHLCV, MA data
            market_ret_10d: Overall market 10-day return for relative strength

        Returns:
            {technical: float, components: {trend, vol, breadth, rel_strength}}
        """
        if not sector_stocks:
            return {'technical': 5.0, 'components': {}}

        closes = []
        ma20s = []
        ma60s = []
        vol5s = []
        vol20s = []
        ret10ds = []

        for stock in sector_stocks:
            c = stock.get('close')
            m20 = stock.get('ma20')
            m60 = stock.get('ma60')
            v5 = stock.get('vol_ma5')
            v20 = stock.get('vol_ma20')
            r10 = stock.get('ret_10d')

            if c and m20:
                closes.append(c)
                ma20s.append(m20)
            if m20 and m60:
                ma60s.append(m60)
            if v5 and v20:
                vol5s.append(v5)
                vol20s.append(v20)
            if r10 is not None:
                ret10ds.append(r10)

        # trend_score
        trend_scores = []
        for c, m20, m60 in zip(closes, ma20s, ma60s):
            if m20 != 0 and m60 != 0:
                s = 5 + 2.5 * ((c - m20) / m20 / 0.1 + (m20 - m60) / m60 / 0.1)
                trend_scores.append(max(0, min(10, s)))
        trend_score = sum(trend_scores) / len(trend_scores) if trend_scores else 5.0

        # vol_score
        vol_scores = []
        for v5, v20 in zip(vol5s, vol20s):
            if v20 != 0:
                vol_ratio = v5 / v20
                s = min(10, max(0, (vol_ratio - 0.8) * 10 / 0.7))
                vol_scores.append(s)
        vol_score = sum(vol_scores) / len(vol_scores) if vol_scores else 5.0

        # breadth_score
        if ma20s:
            above_ma20 = sum(1 for c, m20 in zip(closes, ma20s) if c > m20)
            breadth = above_ma20 / len(ma20s)
            breadth_score = 10 * breadth
        else:
            breadth_score = 5.0

        # rel_strength_score
        if ret10ds:
            avg_ret_10d = sum(ret10ds) / len(ret10ds)
            if market_ret_10d != 0:
                rel_str = avg_ret_10d / market_ret_10d
            else:
                rel_str = 1.0
            rel_strength_score = min(10, max(0, 5 + 5 * (rel_str - 1) / 0.5))
        else:
            rel_strength_score = 5.0

        # Weighted composite
        technical = 0.30 * trend_score + 0.25 * vol_score + 0.30 * breadth_score + 0.15 * rel_strength_score

        return {
            'technical': round(technical, 2),
            'components': {
                'trend': round(trend_score, 2),
                'vol': round(vol_score, 2),
                'breadth': round(breadth_score, 2),
                'rel_strength': round(rel_strength_score, 2),
            }
        }

    def calculate_sentiment_score(self, limit_data: Dict[str, Any],
                                  turnover_data: List[Dict[str, Any]],
                                  total_stocks: int) -> Dict[str, Any]:
        """
        Calculate sentiment score (0-10) for a sector.

        Args:
            limit_data: {lu_count: int, max_board: int} — 涨停家数, 最高连板
            turnover_data: List of stock turnover ratios (5d MA / 20d MA)
            total_stocks: Total number of stocks in sector

        Returns:
            {sentiment: float, components: {lu_heat, max_board, turn_activity}}
        """
        # lu_heat_score
        lu_count = limit_data.get('lu_count', 0)
        if total_stocks > 0:
            lu_ratio = lu_count / total_stocks
            lu_heat_score = min(10, lu_ratio * 50)
        else:
            lu_heat_score = 0.0

        # max_board_score
        max_board = limit_data.get('max_board', 0)
        max_board_score = min(10, max_board * 2)

        # turn_activity_score
        turn_scores = []
        for item in turnover_data:
            turn_ratio = item.get('turn_ratio', 1.0)
            s = min(10, max(0, (turn_ratio - 0.8) * 10 / 0.7))
            turn_scores.append(s)
        turn_activity_score = sum(turn_scores) / len(turn_scores) if turn_scores else 5.0

        # Weighted composite
        sentiment = 0.40 * lu_heat_score + 0.30 * max_board_score + 0.30 * turn_activity_score

        return {
            'sentiment': round(sentiment, 2),
            'components': {
                'lu_heat': round(lu_heat_score, 2),
                'max_board': round(max_board_score, 2),
                'turn_activity': round(turn_activity_score, 2),
            }
        }

    def calculate_composite_strength(self, technical: float, sentiment: float,
                                     capital_score: Optional[float] = None) -> float:
        """
        Calculate composite market strength score (0-1) via sigmoid.
        """
        if capital_score is not None:
            raw = 0.45 * technical + 0.35 * sentiment + 0.20 * capital_score
        else:
            raw = 0.55 * technical + 0.45 * sentiment

        strength_score = sigmoid((raw - 5) / 2)
        return round(strength_score, 4)

    def classify_state(self, strength_score: float, sentiment_score: float,
                      history_data: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Classify market state: weak / normal / overheated.

        Uses sentiment z-score with layered fallback for insufficient history.
        """
        degraded = False
        zscore = 0.0

        if history_data and len(history_data) >= 5:
            mean_val = sum(history_data) / len(history_data)
            if len(history_data) >= 2:
                variance = sum((x - mean_val) ** 2 for x in history_data) / (len(history_data) - 1)
                std_val = math.sqrt(variance) if variance > 0 else 1.0
            else:
                std_val = 1.0

            if std_val > 0:
                zscore = (sentiment_score - mean_val) / std_val
            else:
                zscore = 0.0
        else:
            # Fallback to absolute thresholds
            degraded = True
            # Default threshold for "other" sectors
            absolute_threshold = 8.0
            if sentiment_score > absolute_threshold:
                zscore = 2.0  # Treat as overheated
            else:
                zscore = 0.0

        # State classification
        if strength_score > 0.7 and zscore > 1.5:
            state = 'overheated'
        elif strength_score >= 0.4:
            state = 'normal'
        else:
            state = 'weak'

        return {
            'state': state,
            'zscore': round(zscore, 4),
            'degraded': degraded,
        }

    def calculate_concentration(self, sector_stocks: List[Dict[str, Any]],
                                sector_ret_5d: float = 0.0) -> Dict[str, Any]:
        """
        Calculate leading concentration and rotation speed.

        Args:
            sector_stocks: List with {ret_5d, turnover, code}
            sector_ret_5d: Sector-level 5-day return

        Returns:
            {structure_type, concentration, rotation_speed, status}
        """
        n = len(sector_stocks)
        if n < 10:
            return {
                'structure_type': '无法判断',
                'concentration': None,
                'rotation_speed': None,
                'status': 'too_few_stocks',
            }

        if sector_ret_5d < -0.03:
            return {
                'structure_type': '弱势',
                'concentration': None,
                'rotation_speed': None,
                'status': 'declining',
            }

        # Sort by 5d return
        sorted_stocks = sorted(sector_stocks, key=lambda x: x.get('ret_5d', 0), reverse=True)
        top_20_pct_count = max(1, n // 5)
        top_stocks = sorted_stocks[:top_20_pct_count]

        # Check avg gain of top stocks
        top_avg_gain = sum(s.get('ret_5d', 0) for s in top_stocks) / len(top_stocks) if top_stocks else 0

        if sector_ret_5d < 0 and top_avg_gain > 0.02:
           逆势_suffix = True
        else:
            逆势_suffix = False

        if top_avg_gain < 0.03 and not 逆势_suffix:
            return {
                'structure_type': '弱势',
                'concentration': None,
                'rotation_speed': None,
                'status': 'insufficient_gain',
            }

        # Concentration
        top_turnover = sum(s.get('turnover', 0) for s in top_stocks)
        total_turnover = sum(s.get('turnover', 0) for s in sector_stocks)
        concentration = top_turnover / total_turnover if total_turnover > 0 else 0

        # Structure type
        if concentration > 0.6:
            structure_type = '聚焦'
        elif concentration < 0.4:
            structure_type = '扩散'
        else:
            structure_type = '过渡'

        if 逆势_suffix:
            structure_type += '_逆势'

        return {
            'structure_type': structure_type,
            'concentration': round(concentration, 4),
            'rotation_speed': None,  # Needs yesterday's data
            'status': 'calculated',
        }
