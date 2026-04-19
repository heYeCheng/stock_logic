# -*- coding: utf-8 -*-
"""
StockMapper: L3 multi-sector mapping for Phase 0.5.

Maps stocks to multiple sectors with affiliation strength.
Uses keyword-based matching for logic_match_score.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StockMapper:
    """
    L3 Stock Mapper (Phase 0.5).

    Handles stock-sector affiliations and logic match scoring.
    """

    def __init__(self, anchor_loader=None, tushare_fetcher=None, llm_client=None):
        self.anchor_loader = anchor_loader
        self.tushare_fetcher = tushare_fetcher
        self.llm_client = llm_client
        self._affiliations_cache = {}
        self._keyword_cache = {}
        self._industry_position_cache = {}

    def _get_anchor(self, filename: str) -> dict:
        if self.anchor_loader:
            return self.anchor_loader.load(filename)
        return {}

    def build_affiliations(self, stock_code: str, sw_sector: Optional[str] = None,
                          concept_sectors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Build affiliations for a stock.

        Args:
            stock_code: Stock code
            sw_sector: 申万行业 classification
            concept_sectors: List of 概念板块

        Returns:
            List of {sector_code, type, strength}
        """
        affiliations = []
        anchor = self._get_anchor('affiliation_strength.yaml')

        # Industry sector
        if sw_sector:
            affiliations.append({
                'sector_code': sw_sector,
                'type': 'industry',
                'strength': anchor.get('industry_default', 1.0),
            })

        # Concept sectors
        if concept_sectors:
            for concept in concept_sectors:
                strength = 0.8  # Default strong association
                affiliations.append({
                    'sector_code': concept,
                    'type': 'concept',
                    'strength': strength,
                })

        return affiliations

    def get_logic_match_score(self, stock_code: str, sector_code: str,
                              business_description: str = "") -> float:
        """
        Calculate logic_match_score via keyword matching.

        logic_match_score = 0.6 * keyword_score + 0.4 * industry_position_score
        """
        # Keyword score
        keyword_score = self._calculate_keyword_score(sector_code, business_description)

        # Industry position score
        position_score = self._get_industry_position_score(stock_code, sector_code)

        return 0.6 * keyword_score + 0.4 * position_score

    def _calculate_keyword_score(self, sector_code: str, business_description: str) -> float:
        """
        Match business description against sector keywords.

        Returns:
            0.9 (≥2 keywords), 0.6 (1 keyword), 0.3 (no match)
        """
        if not business_description:
            return 0.3

        keywords = self._get_sector_keywords(sector_code)
        if not keywords:
            return 0.3

        match_count = sum(1 for kw in keywords if kw in business_description)

        if match_count >= 2:
            return 0.9
        elif match_count == 1:
            return 0.6
        else:
            return 0.3

    def _get_sector_keywords(self, sector_code: str) -> List[str]:
        """Get keywords for a sector from cache/anchor."""
        if sector_code in self._keyword_cache:
            return self._keyword_cache[sector_code]

        anchor = self._get_anchor('sector_keywords.yaml')
        keywords = anchor.get(sector_code, [])
        self._keyword_cache[sector_code] = keywords
        return keywords

    def _get_industry_position_score(self, stock_code: str, sector_code: str) -> float:
        """
        Get industry position score from cache/anchor.

        Returns:
            0.9 (直接受益), 0.6 (间接受益), 0.3 (边缘受益), 0.1 (不受益)
        """
        cache_key = f"{stock_code}:{sector_code}"
        if cache_key in self._industry_position_cache:
            return self._industry_position_cache[cache_key]

        anchor = self._get_anchor('industry_position.yaml')
        default_score = anchor.get('default', 0.6)

        # Phase 0.5: use default, LLM-based classification in Phase 0.5.5
        self._industry_position_cache[cache_key] = default_score
        return default_score
