# -*- coding: utf-8 -*-
"""
AsyncCollector base class with retry + fallback.

All collectors inherit from this and implement fetch_data().
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AsyncCollector(ABC):
    """
    Base class for all async data collectors.

    Features:
    - Exponential backoff retry (1s, 2s, 4s) x max_retries
    - Fallback to cached data on collection failure
    - Checkpoint/resume support
    """

    def __init__(
        self,
        datastore,
        max_retries: int = 3,
        base_delay: float = 1.0,
        fallback_enabled: bool = True,
    ):
        self.datastore = datastore
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.fallback_enabled = fallback_enabled

    async def fetch_with_retry(
        self,
        target: str,
        d: date,
        fallback_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data with exponential backoff retry.

        Args:
            target: identifier for the fetch target (e.g., sector name, stock code)
            d: analysis date
            fallback_key: key to fall back to on failure (uses target if None)

        Returns:
            Fetched data dict, or cached data on failure, or None
        """
        fk = fallback_key or target
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.fetch_data(target, d)
                if result is not None:
                    logger.info(f"[{self.__class__.__name__}] fetched {target} for {d.isoformat()}")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[{self.__class__.__name__}] fetch {target} attempt {attempt}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"[{self.__class__.__name__}] all retries failed for {target}: {last_error}")

        if self.fallback_enabled:
            cached = self.datastore.get_snapshot(d, fk)
            if cached is not None:
                logger.info(f"[{self.__class__.__name__}] falling back to cached data for {target}")
                return cached

        return None

    @abstractmethod
    async def fetch_data(self, target: str, d: date) -> Optional[Dict[str, Any]]:
        """
        Implement actual data fetching.
        Must be async. Returns data dict or None.
        """
        ...

    @abstractmethod
    def get_targets(self, d: date) -> list:
        """
        Return list of targets to fetch for the given date.
        e.g., list of sector names, list of stock codes.
        """
        ...
