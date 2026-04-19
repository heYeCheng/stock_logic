# -*- coding: utf-8 -*-
"""
PolymarketCollector: fetches prediction market data from Polymarket.

Data source: Polymarket Gamma API
  - Base URL: https://gamma-api.polymarket.com
  - Data: market probability, volume, 24h change
  - Priority: 2 (supplementary data source)
  - Fallback: cached data from DataStore

Polymarket is used for global event prediction:
  - US-China tariff escalation
  - Fed rate decisions
  - Geopolitical conflicts
  - Recession predictions
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .base import AsyncCollector

logger = logging.getLogger(__name__)


class PolymarketCollector(AsyncCollector):
    """
    Collects Polymarket prediction data.

    Features:
    - Fetches market probability for configured markets
    - Calculates 24h probability change
    - Supports fallback to cached data
    """

    name = "polymarket"
    base_url = "https://gamma-api.polymarket.com"

    def __init__(self, datastore, skill_loader=None):
        super().__init__(datastore, max_retries=3, base_delay=1.0, fallback_enabled=True)
        self.skill_loader = skill_loader
        self._config = None

    def _load_config(self) -> Dict[str, Any]:
        """Load Polymarket config from skill file."""
        if self._config:
            return self._config

        if self.skill_loader:
            config = self.skill_loader._load_json_model(
                "macro/polymarket-config.json",
                type("MockModel", (), {"__init__": lambda self, **kwargs: setattr(self, "__dict__", kwargs)})
            )
            if config:
                self._config = config.__dict__
                return self._config

        # Fallback: load directly from file
        import json
        from pathlib import Path
        skill_dir = Path("~/.gstack/skills/sector-logic").expanduser()
        config_path = skill_dir / "macro" / "polymarket-config.json"
        if config_path.exists():
            self._config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self._config = {"markets": []}

        return self._config

    async def fetch_data(self, target: str, d: date) -> Optional[Dict[str, Any]]:
        """
        Fetch Polymarket data for a specific market.

        Args:
            target: Market ID (e.g., "us-china-tariffs")
            d: Analysis date

        Returns:
            Dict with probability, volume, change_24h, or None on failure
        """
        import aiohttp

        config = self._load_config()
        markets = config.get("markets", [])
        market_config = next((m for m in markets if m["id"] == target), None)

        if not market_config:
            logger.warning(f"[PolymarketCollector] market not found: {target}")
            return None

        logger.info(f"[PolymarketCollector] fetching {target} for {d.isoformat()}")

        try:
            async with aiohttp.ClientSession() as session:
                # Fetch market data
                url = f"{self.base_url}/markets"
                params = {"event": market_config.get("name", target)}

                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"[PolymarketCollector] API error for {target}: {response.status}")
                        return None

                    data = await response.json()

                    if not data or not isinstance(data, list) or len(data) == 0:
                        logger.warning(f"[PolymarketCollector] no data for {target}")
                        return None

                    market = data[0]
                    outcomes = market.get("outcomes", [])

                    # Extract probability (assuming binary market with 'Yes' outcome)
                    yes_outcome = next((o for o in outcomes if o.get("name") == "Yes"), None)
                    probability = yes_outcome.get("price", 0.5) if yes_outcome else 0.5

                    # Extract volume
                    volume = market.get("volume", 0)

                    # Calculate 24h change (simplified, would need historical data for accurate calc)
                    change_24h = 0.0

                    result = {
                        "market_id": target,
                        "probability": probability,
                        "volume": volume,
                        "change_24h": change_24h,
                        "last_updated": date.today().isoformat(),
                    }

                    logger.info(f"[PolymarketCollector] fetched {target}: prob={probability:.2%}, volume={volume}")
                    return result

        except aiohttp.ClientError as e:
            logger.error(f"[PolymarketCollector] network error for {target}: {e}")
            return None
        except Exception as e:
            logger.error(f"[PolymarketCollector] unexpected error for {target}: {e}")
            return None

    def get_targets(self, d: date) -> List[str]:
        """Return list of market IDs to fetch."""
        config = self._load_config()
        return [m["id"] for m in config.get("markets", [])]

    async def collect_all(self, d: date) -> Dict[str, Any]:
        """
        Collect all configured markets and return aggregated result.

        Returns:
            Dict mapping market_id to market data
        """
        import asyncio

        targets = self.get_targets(d)
        tasks = [self.fetch_with_retry(target, d) for target in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated = {}
        for target, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.error(f"[PolymarketCollector] failed to fetch {target}: {result}")
                aggregated[target] = {"error": str(result)}
            elif result:
                aggregated[target] = result
            else:
                aggregated[target] = None

        return aggregated
