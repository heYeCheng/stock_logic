# -*- coding: utf-8 -*-
"""
StockRadarScorer: computes individual stock four-dimension radar scores.

Input:
  - Stock data (fundamentals, price/volume, news sentiment)
  - Sector logic result (from SectorAgent)
  - Skill files: stock/four-dimension-radar.json, stock/scoring-rules.json

Process:
  1. Load radar config and scoring rules
  2. Score each dimension (0-10):
     - Logic face: inherits sector logic strength
     - Fundamentals: PE/PB/ROE/revenue growth/gross margin
     - Technical: price vs MA, volume trend, momentum
     - Sentiment: FinBERT news sentiment, search trend
  3. Compute weighted average → stock_thesis_score (0-1)

Output:
  - stock_radar_scores: {logic, fundamental, technical, sentiment}
  - stock_thesis_score: overall score (0-1)
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StockRadarScorer:
    """
    Computes individual stock four-dimension radar scores.
    """

    def __init__(self, skill_loader):
        self.skill_loader = skill_loader
        self._radar_config = None
        self._scoring_rules = None

    def _load_radar_config(self) -> Dict[str, Any]:
        """Load four-dimension radar config."""
        if self._radar_config:
            return self._radar_config

        self._radar_config = self.skill_loader.load_stock_config("four-dimension-radar.json")
        if not self._radar_config:
            self._radar_config = self._get_default_radar_config()

        return self._radar_config

    def _load_scoring_rules(self) -> Dict[str, Any]:
        """Load scoring rules."""
        if self._scoring_rules:
            return self._scoring_rules

        self._scoring_rules = self.skill_loader.load_stock_config("scoring-rules.json")
        if not self._scoring_rules:
            self._scoring_rules = self._get_default_scoring_rules()

        return self._scoring_rules

    def _get_default_radar_config(self) -> Dict[str, Any]:
        """Default radar config if skill file not found."""
        return {
            "dimensions": [
                {"name": "逻辑面", "weight": 0.3},
                {"name": "基本面", "weight": 0.25},
                {"name": "技术面", "weight": 0.25},
                {"name": "情绪面", "weight": 0.2},
            ]
        }

    def _get_default_scoring_rules(self) -> Dict[str, Any]:
        """Default scoring rules if skill file not found."""
        return {
            "fundamental": {
                "pe_score_formula": "10 - pe_percentile / 10",
                "pb_score_formula": "10 - pb_percentile / 10",
                "roe_threshold": 15,
                "revenue_growth_threshold": 20,
            },
            "technical": {
                "ma20_weight": 0.4,
                "ma60_weight": 0.3,
                "volume_weight": 0.3,
            },
        }

    async def score(
        self,
        stock_code: str,
        stock_data: Dict[str, Any],
        sector_result: Optional[Dict[str, Any]] = None,
        d: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Compute stock radar scores.

        Args:
            stock_code: Stock ticker (e.g., "600519")
            stock_data: Stock data with fundamentals, technicals, sentiment
            sector_result: Sector logic result from SectorAgent
            d: Analysis date

        Returns:
            Dict with stock_radar_scores and stock_thesis_score
        """
        logger.info(f"[StockRadarScorer] scoring {stock_code}")

        radar_config = self._load_radar_config()
        scoring_rules = self._load_scoring_rules()

        # Score each dimension
        logic_score = self._score_logic(stock_data, sector_result, scoring_rules)
        fundamental_score = self._score_fundamental(stock_data, scoring_rules)
        technical_score = self._score_technical(stock_data, scoring_rules)
        sentiment_score = self._score_sentiment(stock_data, scoring_rules)

        # Compute weighted average
        dimensions = radar_config.get("dimensions", [])
        weights = {dim["name"]: dim["weight"] for dim in dimensions}

        total_score = (
            logic_score * weights.get("逻辑面", 0.3)
            + fundamental_score * weights.get("基本面", 0.25)
            + technical_score * weights.get("技术面", 0.25)
            + sentiment_score * weights.get("情绪面", 0.2)
        )

        stock_thesis_score = round(total_score / 10.0, 4)  # Normalize to 0-1

        result = {
            "stock_code": stock_code,
            "analysis_date": d.isoformat() if d else None,
            "stock_radar_scores": {
                "logic": round(logic_score, 2),
                "fundamental": round(fundamental_score, 2),
                "technical": round(technical_score, 2),
                "sentiment": round(sentiment_score, 2),
            },
            "stock_thesis_score": stock_thesis_score,
            "sector_logic_strength": sector_result.get("sector_logic_strength") if sector_result else None,
        }

        logger.info(f"[StockRadarScorer] {stock_code} thesis_score={stock_thesis_score:.2f}")
        return result

    def _score_logic(
        self,
        stock_data: Dict[str, Any],
        sector_result: Optional[Dict[str, Any]],
        scoring_rules: Dict[str, Any],
    ) -> float:
        """Score logic dimension (0-10)."""
        # Inherit sector logic strength
        if sector_result:
            sector_strength = sector_result.get("sector_logic_strength", 0.5)
            logic_correlation = stock_data.get("logic_correlation", 0.8)
            score = sector_strength * logic_correlation * 10
        else:
            score = 5.0

        # Adjust by stock's own logic thesis if available
        stock_thesis = stock_data.get("stock_logic_thesis", None)
        if stock_thesis:
            score = (score + stock_thesis * 10) / 2

        return max(0.0, min(10.0, score))

    def _score_fundamental(
        self,
        stock_data: Dict[str, Any],
        scoring_rules: Dict[str, Any],
    ) -> float:
        """Score fundamental dimension (0-10)."""
        rules = scoring_rules.get("fundamental", {})
        score = 5.0  # Default neutral

        pe_percentile = stock_data.get("pe_percentile")
        pb_percentile = stock_data.get("pb_percentile")
        roe = stock_data.get("roe")
        revenue_growth = stock_data.get("revenue_growth")
        gross_margin_trend = stock_data.get("gross_margin_trend")

        subscores = []

        # PE score: lower percentile = higher score
        if pe_percentile is not None:
            pe_score = 10 - (pe_percentile / 100.0 * 10)
            subscores.append(pe_score)

        # PB score: lower percentile = higher score
        if pb_percentile is not None:
            pb_score = 10 - (pb_percentile / 100.0 * 10)
            subscores.append(pb_score)

        # ROE score: > 15% = high score
        roe_threshold = rules.get("roe_threshold", 15)
        if roe is not None:
            if roe > roe_threshold * 1.5:
                roe_score = 9.5
            elif roe > roe_threshold:
                roe_score = 8.0
            elif roe > roe_threshold * 0.5:
                roe_score = 5.5
            else:
                roe_score = 3.0
            subscores.append(roe_score)

        # Revenue growth score
        growth_threshold = rules.get("revenue_growth_threshold", 20)
        if revenue_growth is not None:
            if revenue_growth > growth_threshold * 2:
                growth_score = 9.5
            elif revenue_growth > growth_threshold:
                growth_score = 8.0
            elif revenue_growth > 0:
                growth_score = 5.5
            else:
                growth_score = 2.5
            subscores.append(growth_score)

        # Gross margin trend
        if gross_margin_trend is not None:
            if gross_margin_trend > 0.05:  # Improving > 5%
                trend_score = 8.5
            elif gross_margin_trend > 0:
                trend_score = 6.5
            elif gross_margin_trend > -0.05:
                trend_score = 4.0
            else:
                trend_score = 2.0
            subscores.append(trend_score)

        if subscores:
            score = sum(subscores) / len(subscores)

        return max(0.0, min(10.0, score))

    def _score_technical(
        self,
        stock_data: Dict[str, Any],
        scoring_rules: Dict[str, Any],
    ) -> float:
        """Score technical dimension (0-10)."""
        tech_rules = scoring_rules.get("technical", {})
        subscores = []

        price = stock_data.get("price", 0)
        ma20 = stock_data.get("ma20")
        ma60 = stock_data.get("ma60")
        volume_ratio = stock_data.get("volume_ratio")
        momentum = stock_data.get("momentum_pct", 0)

        # Price vs MA20
        if ma20 and price:
            if price > ma20 * 1.05:
                ma20_score = 9.0
            elif price > ma20:
                ma20_score = 7.0
            elif price > ma20 * 0.95:
                ma20_score = 4.5
            else:
                ma20_score = 2.0
            subscores.append(ma20_score)

        # Price vs MA60
        if ma60 and price:
            if price > ma60 * 1.1:
                ma60_score = 9.0
            elif price > ma60:
                ma60_score = 7.0
            elif price > ma60 * 0.95:
                ma60_score = 4.0
            else:
                ma60_score = 2.0
            subscores.append(ma60_score)

        # Volume trend
        if volume_ratio is not None:
            if volume_ratio > 2.0:
                vol_score = 8.5
            elif volume_ratio > 1.5:
                vol_score = 7.0
            elif volume_ratio > 0.8:
                vol_score = 5.5
            else:
                vol_score = 3.5
            subscores.append(vol_score)

        # Momentum (not too extreme)
        if momentum is not None:
            if 2 < momentum < 15:  # Moderate uptrend preferred
                mom_score = 8.0
            elif 0 < momentum <= 2:
                mom_score = 6.5
            elif momentum > 15:
                mom_score = 5.0  # Overbought risk
            elif -5 < momentum <= 0:
                mom_score = 4.0
            else:
                mom_score = 2.0
            subscores.append(mom_score)

        if subscores:
            score = sum(subscores) / len(subscores)
        else:
            score = 5.0

        return max(0.0, min(10.0, score))

    def _score_sentiment(
        self,
        stock_data: Dict[str, Any],
        scoring_rules: Dict[str, Any],
    ) -> float:
        """Score sentiment dimension (0-10)."""
        subscores = []

        news_sentiment = stock_data.get("news_sentiment_score")
        news_volume = stock_data.get("positive_news_count")
        search_trend = stock_data.get("search_trend_change")

        # FinBERT sentiment
        if news_sentiment is not None:
            if news_sentiment > 0.7:
                sent_score = 9.0
            elif news_sentiment > 0.5:
                sent_score = 7.5
            elif news_sentiment > 0.2:
                sent_score = 5.5
            elif news_sentiment > -0.2:
                sent_score = 4.0
            else:
                sent_score = 2.0
            subscores.append(sent_score)

        # Positive news volume
        if news_volume is not None:
            if news_volume > 5:
                news_score = 8.5
            elif news_volume > 3:
                news_score = 7.0
            elif news_volume > 1:
                news_score = 5.5
            else:
                news_score = 4.0
            subscores.append(news_score)

        # Search trend
        if search_trend is not None:
            if search_trend > 30:
                search_score = 9.0
            elif search_trend > 10:
                search_score = 7.5
            elif search_trend > 0:
                search_score = 6.0
            elif search_trend > -10:
                search_score = 4.0
            else:
                search_score = 2.0
            subscores.append(search_score)

        if subscores:
            score = sum(subscores) / len(subscores)
        else:
            score = 5.0

        return max(0.0, min(10.0, score))
