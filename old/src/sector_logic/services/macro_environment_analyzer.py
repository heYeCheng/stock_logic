# -*- coding: utf-8 -*-
"""
MacroEnvironmentAnalyzer: L0 macro environment layer for Phase 0.5.

4-quadrant classification (货币-信用框架) + global multiplier + event-triggered adjustments.

Usage:
    analyzer = MacroEnvironmentAnalyzer(anchor_loader, macro_event_repo)
    result = analyzer.analyze(pmi=50.5, m1_m2_diff=-1.2, shibor_trend='up')
    # result: {multiplier, quadrant, status, alignment_status, updated_at}
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Quadrant definitions with default thresholds
QUADRANT_RULES = {
    '宽信用期': {'pmi_min': 50, 'm1_m2_direction': 'narrowing', 'multiplier': 1.10},
    '紧流动性期': {'pmi_min': 50, 'shibor_trend': 'up', 'multiplier': 0.95},
    '双紧期': {'pmi_max': 50, 'liquidity': 'tightening', 'multiplier': 0.90},
    '宽货币期': {'pmi_max': 50, 'policy': 'easing', 'multiplier': 1.05},
    '中性': {'multiplier': 1.00},
}

CLAMP_RANGE = (0.85, 1.15)


class MacroEnvironmentAnalyzer:
    """
    L0 Macro Environment Analyzer (Phase 0.5).

    Replaces the 5-dimension scoring with a 4-quadrant + global multiplier system.
    Supports event-triggered adjustments (manual entry).
    """

    def __init__(self, anchor_loader=None, macro_event_repo=None):
        self.anchor_loader = anchor_loader
        self.macro_event_repo = macro_event_repo
        self._anchor_cache = {}

    def _get_anchor(self, key: str) -> dict:
        """Load anchor with caching."""
        if key not in self._anchor_cache:
            if self.anchor_loader:
                self._anchor_cache[key] = self.anchor_loader.load(key)
            else:
                self._anchor_cache[key] = {}
        return self._anchor_cache[key]

    def classify_quadrant(self, pmi: Optional[float], m1_m2_diff: Optional[float],
                          shibor_trend: str = 'neutral', policy_easing: bool = False,
                          liquidity_tightening: bool = False) -> Dict[str, Any]:
        """
        Classify macro environment into 4 quadrants + neutral.

        Args:
            pmi: PMI new orders index (>50 = expansion)
            m1_m2_diff: M1-M2 剪刀差 (positive = narrowing/turning positive)
            shibor_trend: 'up' / 'down' / 'neutral'
            policy_easing: True if recent rate cut / RRR cut
            liquidity_tightening: True if liquidity is tightening

        Returns:
            {quadrant: str, base_multiplier: float}
        """
        anchor = self._get_anchor('macro_anchor.yaml')
        thresholds = anchor.get('pmi_thresholds', {})
        multipliers = anchor.get('quadrant_multipliers', {})

        pmi_strong = thresholds.get('strong_expansion', 52)
        pmi_weak_low = thresholds.get('weak_expansion_low', 50)
        pmi_contract_low = thresholds.get('contraction_low', 48)

        # Determine growth direction
        if pmi is not None:
            growth_up = pmi >= pmi_weak_low
            growth_strong = pmi >= pmi_strong
        else:
            growth_up = False
            growth_strong = False

        # Determine liquidity direction
        m1m2_narrowing = m1_m2_diff is not None and m1_m2_diff > 0
        shibor_up = shibor_trend == 'up'

        # 4-quadrant classification (货币-信用框架)
        if growth_up and m1m2_narrowing:
            quadrant = '宽信用期'
            multiplier = multipliers.get('wide_credit', 1.10)
        elif growth_up and shibor_up:
            quadrant = '紧流动性期'
            multiplier = multipliers.get('tight_liquidity', 0.95)
        elif not growth_up and liquidity_tightening:
            quadrant = '双紧期'
            multiplier = multipliers.get('double_tight', 0.90)
        elif not growth_up and policy_easing:
            quadrant = '宽货币期'
            multiplier = multipliers.get('wide_money', 1.05)
        else:
            quadrant = '中性'
            multiplier = multipliers.get('neutral', 1.00)

        return {'quadrant': quadrant, 'base_multiplier': multiplier}

    def calculate_multiplier(self, pmi: Optional[float] = None,
                             m1_m2_diff: Optional[float] = None,
                             shibor_trend: str = 'neutral',
                             policy_easing: bool = False,
                             liquidity_tightening: bool = False,
                             data_available: bool = True) -> Dict[str, Any]:
        """
        Calculate macro_multiplier with event-triggered adjustments.

        Args:
            pmi: PMI new orders index
            m1_m2_diff: M1-M2 剪刀差
            shibor_trend: Shibor trend direction
            policy_easing: True if recent policy easing
            liquidity_tightening: True if liquidity tightening
            data_available: False if macro data is unavailable

        Returns:
            {
                multiplier: float (clamped to [0.85, 1.15]),
                quadrant: str,
                status: str,
                alignment_status: str,
                event_adjustment: float,
                updated_at: str
            }
        """
        if not data_available:
            return {
                'multiplier': 1.00,
                'quadrant': '中性',
                'status': 'MACRO_DATA_UNAVAILABLE',
                'alignment_status': '数据缺失',
                'event_adjustment': 0.0,
                'updated_at': datetime.now().isoformat(),
            }

        # Step 1: Classify quadrant and get base multiplier
        quadrant_result = self.classify_quadrant(
            pmi=pmi, m1_m2_diff=m1_m2_diff,
            shibor_trend=shibor_trend,
            policy_easing=policy_easing,
            liquidity_tightening=liquidity_tightening,
        )
        base_multiplier = quadrant_result['base_multiplier']
        quadrant = quadrant_result['quadrant']

        # Step 2: Apply event-triggered adjustments
        event_adjustment = 0.0
        if self.macro_event_repo:
            event_adjustment = self.macro_event_repo.get_total_adjustment()

        # Step 3: Calculate and clamp
        raw_multiplier = base_multiplier + event_adjustment
        clamp_range = self._get_anchor('macro_anchor.yaml').get('clamp_range', CLAMP_RANGE)
        multiplier = max(clamp_range[0], min(clamp_range[1], raw_multiplier))

        # Determine alignment status
        alignment_status = '完整数据'

        return {
            'multiplier': round(multiplier, 4),
            'quadrant': quadrant,
            'status': 'active',
            'alignment_status': alignment_status,
            'event_adjustment': round(event_adjustment, 4),
            'updated_at': datetime.now().isoformat(),
        }
