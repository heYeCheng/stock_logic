# -*- coding: utf-8 -*-
"""
ExecutionLayer: L4 execution decision layer for Phase 0.5.

Replaces the discrete decision matrix with a continuous position function
and A-share trading constraints.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionLayer:
    """
    L4 Execution Layer (Phase 0.5).

    Continuous position function + A-share trading constraints + recommendation generation.
    """

    def __init__(self, anchor_loader=None):
        self.anchor_loader = anchor_loader
        self._weights = None
        self._thresholds = None

    def _load_weights(self):
        """Load position weights from config file."""
        if self._weights is None:
            if self.anchor_loader:
                data = self.anchor_loader.load('position_weights.yaml')
            else:
                # Fallback: load from config directory
                import yaml
                config_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    'config', 'position_weights.yaml'
                )
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        data = yaml.safe_load(f)
                else:
                    data = {}

            self._weights = data.get('position_weights', {
                'net_thrust': 0.4,
                'stock_composite': 0.4,
                'market_strength': 0.2,
            })
            self._thresholds = data.get('position_thresholds', {
                'heavy': 0.75,
                'medium': 0.50,
                'light': 0.30,
            })

    def calculate_position(self, net_thrust: float, stock_composite_score: float,
                          market_strength_score: float, macro_multiplier: float = 1.0,
                          has_headwind: bool = False,
                          sector_structure_type: str = "") -> Dict[str, Any]:
        """
        Calculate position recommendation via continuous function.

        position_score = (normalized_net_thrust × w_net_thrust
                         + stock_composite_score × w_stock_composite
                         + market_strength_score × w_market_strength)
                        × macro_multiplier
        """
        self._load_weights()

        # Normalize net_thrust to 0-1
        normalized_net_thrust = (max(-1.0, min(1.0, net_thrust)) + 1.0) / 2.0

        w = self._weights
        position_score = (
            normalized_net_thrust * w.get('net_thrust', 0.4)
            + stock_composite_score * w.get('stock_composite', 0.4)
            + market_strength_score * w.get('market_strength', 0.2)
        ) * macro_multiplier

        # Apply risk adjustments
        if has_headwind:
            position_score *= 0.85

        if sector_structure_type == '快速轮动':
            position_score *= 0.80

        # Map to position
        t = self._thresholds
        if position_score > t.get('heavy', 0.75):
            position = '重仓'
        elif position_score > t.get('medium', 0.50):
            position = '半仓'
        elif position_score > t.get('light', 0.30):
            position = '轻仓'
        else:
            position = '观察'

        return {
            'position': position,
            'position_score': round(position_score, 4),
            'raw_score': round(position_score, 4),
        }

    def check_trading_constraints(self, stock_code: str, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check A-share trading constraints.

        Handles different limit rules for different board types.
        """
        prev_close = stock_data.get('prev_close')
        current_price = stock_data.get('close', prev_close)
        pct_chg = stock_data.get('pct_chg', 0)
        board_type = stock_data.get('board_type', 'main')  # main / sci_tech / chi_next
        is_suspended = stock_data.get('is_suspended', False)
        ret_5d = stock_data.get('ret_5d', 0)

        result = {
            'can_buy': True,
            'can_sell': True,
            'warning': None,
            'adjusted_position': None,
        }

        # Check suspension
        if is_suspended:
            result['can_buy'] = False
            result['can_sell'] = False
            result['warning'] = '停牌中'
            return result

        # Calculate limit prices
        if board_type in ('sci_tech', 'chi_next'):
            # 科创板/创业板: ±20%
            limit_up = round(prev_close * 1.20, 2) if prev_close else None
            limit_down = round(prev_close * 0.80, 2) if prev_close else None
        else:
            # 主板/中小板: ±10%
            limit_up = round(prev_close * 1.10, 2) if prev_close else None
            limit_down = round(prev_close * 0.90, 2) if prev_close else None

        # Check if limit up/down
        is_limit_up = False
        is_limit_down = False

        if limit_up and current_price and current_price >= limit_up:
            is_limit_up = True
        if limit_down and current_price and current_price <= limit_down:
            is_limit_down = True

        if is_limit_up:
            result['can_buy'] = False
            if board_type in ('sci_tech', 'chi_next'):
                result['warning'] = '涨停，极高风险，等待分歧'
            else:
                result['warning'] = '观察，等待分歧'
            return result

        if is_limit_down:
            result['can_buy'] = False
            result['can_sell'] = False
            result['warning'] = '跌停，无法卖出'
            return result

        # Check追高风险
        if board_type in ('sci_tech', 'chi_next'):
            if pct_chg > 15:
                result['adjusted_position'] = '降一档'
                result['warning'] = '追高风险'
        else:
            if pct_chg > 7:
                result['adjusted_position'] = '降一档'
                result['warning'] = '追高风险'

        if ret_5d > 0.30:
            result['adjusted_position'] = '降一档'
            result['warning'] = '追高风险'

        return result

    def check_stop_loss(self, peak_strength: float, current_strength: float,
                        market_state: str = 'normal',
                        sector_structure: str = '') -> Dict[str, Any]:
        """
        Check stop loss and holding rules.
        """
        # Rolling peak strength drawdown
        if peak_strength - current_strength > 0.15:
            return {'action': 'reduce', 'reason': '逻辑强度较高点回撤>0.15'}

        # Market state degradation
        if market_state == 'weak':
            return {'action': 'exit', 'reason': '市场状态降为weak'}

        # Sector structure deterioration
        if sector_structure == '快速轮动':
            return {'action': 'reduce', 'reason': '板块结构变为快速轮动'}

        return {'action': 'hold', 'reason': '维持当前持仓'}

    def generate_recommendation_tag(self, logic_match_score: float,
                                    market_score: float) -> str:
        """
        Generate recommendation tag based on logic match and market score.
        """
        if logic_match_score >= 0.7:
            return '逻辑受益股'
        elif logic_match_score >= 0.4:
            return '关联受益股'
        elif market_score > 0.6:
            return '情绪跟风股'
        else:
            return '观察'
