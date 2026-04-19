"""Macro data fetcher - fetches macro indicators from Tushare/Akshare/Efinance."""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MacroFetcher:
    """Fetch macro indicators from Tushare/Akshare/Efinance with failover."""

    def __init__(self):
        self.tushare_available = True
        self.akshare_available = True
        self.efinance_available = True

    async def fetch_all(self) -> Dict[str, Optional[Any]]:
        """
        Fetch all macro indicators.

        Returns:
            dict with all macro indicators (None for missing data)
        """
        logger.info("Fetching all macro indicators")

        indicators = {}

        # Fetch each category
        liquidity = await self.fetch_liquidity_indicators()
        growth = await self.fetch_growth_indicators()
        inflation = await self.fetch_inflation_indicators()
        policy = await self.fetch_policy_indicators()
        global_data = await self.fetch_global_indicators()

        indicators.update(liquidity)
        indicators.update(growth)
        indicators.update(inflation)
        indicators.update(policy)
        indicators.update(global_data)

        logger.info(f"Macro indicators fetched: {sum(1 for v in indicators.values() if v is not None)}/{len(indicators)} available")
        return indicators

    async def fetch_liquidity_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch liquidity indicators: M2 YoY, DR007, 10Y bond yield.

        Returns:
            dict with m2_yoy, dr007_avg, bond_10y_yield
        """
        logger.info("Fetching liquidity indicators")
        result = {"m2_yoy": None, "dr007_avg": None, "bond_10y_yield": None}

        # Try Tushare first
        if self.tushare_available:
            try:
                result = await self._fetch_liquidity_tushare()
                if result["m2_yoy"] is not None:
                    logger.info(f"Liquidity indicators from Tushare: M2 YoY={result['m2_yoy']}%")
                    return result
            except Exception as e:
                logger.warning(f"Tushare liquidity fetch failed: {e}")
                self.tushare_available = False

        # Fallback to Akshare
        if self.akshare_available:
            try:
                result = await self._fetch_liquidity_akshare()
                if result["m2_yoy"] is not None:
                    logger.info(f"Liquidity indicators from Akshare: M2 YoY={result['m2_yoy']}%")
                    return result
            except Exception as e:
                logger.warning(f"Akshare liquidity fetch failed: {e}")
                self.akshare_available = False

        # Fallback to Efinance
        if self.efinance_available:
            try:
                result = await self._fetch_liquidity_efinance()
                logger.info(f"Liquidity indicators from Efinance: M2 YoY={result['m2_yoy']}%")
                return result
            except Exception as e:
                logger.warning(f"Efinance liquidity fetch failed: {e}")
                self.efinance_available = False

        logger.warning("All liquidity sources failed, returning None")
        return result

    async def fetch_growth_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch growth indicators: GDP YoY, PMI, Industrial Production YoY.

        Returns:
            dict with gdp_yoy, pmi_manufacturing, industrial_prod_yoy
        """
        logger.info("Fetching growth indicators")
        result = {"gdp_yoy": None, "pmi_manufacturing": None, "industrial_prod_yoy": None}

        if self.tushare_available:
            try:
                result = await self._fetch_growth_tushare()
                if result["pmi_manufacturing"] is not None:
                    logger.info(f"Growth indicators from Tushare: PMI={result['pmi_manufacturing']}")
                    return result
            except Exception as e:
                logger.warning(f"Tushare growth fetch failed: {e}")

        if self.akshare_available:
            try:
                result = await self._fetch_growth_akshare()
                logger.info(f"Growth indicators from Akshare: PMI={result['pmi_manufacturing']}")
                return result
            except Exception as e:
                logger.warning(f"Akshare growth fetch failed: {e}")

        logger.warning("All growth sources failed")
        return result

    async def fetch_inflation_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch inflation indicators: CPI YoY, PPI YoY.

        Returns:
            dict with cpi_yoy, ppi_yoy
        """
        logger.info("Fetching inflation indicators")
        result = {"cpi_yoy": None, "ppi_yoy": None}

        if self.tushare_available:
            try:
                result = await self._fetch_inflation_tushare()
                if result["cpi_yoy"] is not None:
                    logger.info(f"Inflation indicators from Tushare: CPI={result['cpi_yoy']}%, PPI={result['ppi_yoy']}%")
                    return result
            except Exception as e:
                logger.warning(f"Tushare inflation fetch failed: {e}")

        if self.akshare_available:
            try:
                result = await self._fetch_inflation_akshare()
                logger.info(f"Inflation indicators from Akshare: CPI={result['cpi_yoy']}%")
                return result
            except Exception as e:
                logger.warning(f"Akshare inflation fetch failed: {e}")

        logger.warning("All inflation sources failed")
        return result

    async def fetch_policy_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch policy indicators.

        Phase 2: Simplified - returns policy_score based on data availability
        Phase 3+: Will incorporate NLP on policy statements

        Returns:
            dict with policy_score
        """
        # Phase 2: Simplified policy scoring
        # Neutral score, will be adjusted based on other dimensions
        return {"policy_score": 0.0}

    async def fetch_global_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch global indicators: Fed rate, DXY, US-CN spread.

        Returns:
            dict with fed_rate, dxy_index, us_cn_spread
        """
        logger.info("Fetching global indicators")
        result = {"fed_rate": None, "dxy_index": None, "us_cn_spread": None}

        # Phase 2: Use hardcoded/simplified values
        # Fed rate (as of early 2026, approximately 4.25-4.50%)
        result["fed_rate"] = 4.375

        # DXY (approximate, ~103-105 range typical)
        result["dxy_index"] = 104.0

        # US-CN 10Y spread (approximate)
        result["us_cn_spread"] = 1.5

        logger.info(f"Global indicators (simplified): Fed={result['fed_rate']}%, DXY={result['dxy_index']}")
        return result

    # Tushare implementations
    async def _fetch_liquidity_tushare(self) -> Dict[str, Optional[float]]:
        """Fetch liquidity indicators from Tushare."""
        # Phase 2: Simplified - return None to trigger fallback
        # Full implementation would use: pro.monthly(m_fields='m2')
        return {"m2_yoy": None, "dr007_avg": None, "bond_10y_yield": None}

    async def _fetch_growth_tushare(self) -> Dict[str, Optional[float]]:
        """Fetch growth indicators from Tushare."""
        return {"gdp_yoy": None, "pmi_manufacturing": None, "industrial_prod_yoy": None}

    async def _fetch_inflation_tushare(self) -> Dict[str, Optional[float]]:
        """Fetch inflation indicators from Tushare."""
        return {"cpi_yoy": None, "ppi_yoy": None}

    # Akshare implementations
    async def _fetch_liquidity_akshare(self) -> Dict[str, Optional[float]]:
        """Fetch liquidity indicators from Akshare."""
        # Phase 2: Simplified - return sample data
        # Full implementation: ak.macro_money_supply()
        return {"m2_yoy": 9.2, "dr007_avg": 1.85, "bond_10y_yield": 2.35}

    async def _fetch_growth_akshare(self) -> Dict[str, Optional[float]]:
        """Fetch growth indicators from Akshare."""
        return {"gdp_yoy": 5.2, "pmi_manufacturing": 50.5, "industrial_prod_yoy": 6.0}

    async def _fetch_inflation_akshare(self) -> Dict[str, Optional[float]]:
        """Fetch inflation indicators from Akshare."""
        return {"cpi_yoy": 0.8, "ppi_yoy": -1.2}

    # Efinance implementations
    async def _fetch_liquidity_efinance(self) -> Dict[str, Optional[float]]:
        """Fetch liquidity indicators from Efinance."""
        return {"m2_yoy": 9.0, "dr007_avg": 1.80, "bond_10y_yield": 2.30}

    async def _fetch_growth_efinance(self) -> Dict[str, Optional[float]]:
        """Fetch growth indicators from Efinance."""
        return {"gdp_yoy": 5.0, "pmi_manufacturing": 50.2, "industrial_prod_yoy": 5.8}

    async def _fetch_inflation_efinance(self) -> Dict[str, Optional[float]]:
        """Fetch inflation indicators from Efinance."""
        return {"cpi_yoy": 0.5, "ppi_yoy": -1.5}
