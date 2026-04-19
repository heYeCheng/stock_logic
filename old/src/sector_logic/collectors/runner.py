# -*- coding: utf-8 -*-
"""
CollectionRunner: orchestrates the full data collection pipeline.

Uses asyncio.gather for concurrent collection:
  1. MacroCollector (1 target)
  2. SectorCollector (N sectors, concurrent)
  3. StockCollector (M stocks, concurrent)

All results are written to DataStore as snapshots.
"""

import asyncio
import logging
from datetime import date
from typing import Optional

from src.sector_logic.datastore import DataStore
from src.sector_logic.collectors.macro_collector import MacroCollector
from src.sector_logic.collectors.sector_collector import SectorCollector
from src.sector_logic.collectors.stock_collector import StockCollector

logger = logging.getLogger(__name__)


class CollectionRunner:
    """
    Orchestrates data collection for a given date.

    Flow:
      1. Check checkpoint (resume if partial)
      2. Collect macro data (weekly, or if missing)
      3. Collect sector data (all sectors, concurrent)
      4. Collect stock data (all stocks, concurrent)
      5. Write all results to DataStore
      6. Clear checkpoint on success
    """

    def __init__(
        self,
        datastore=None,
        max_concurrency: int = 10,
        sectors=None,
        stock_codes=None,
        use_pilot: bool = False,
        **common_kwargs,
    ):
        self.datastore = datastore or DataStore()
        self.max_concurrency = max_concurrency
        self.sectors = sectors
        self.stock_codes = stock_codes
        self.use_pilot = use_pilot
        self.common_kwargs = common_kwargs

    async def run(self, d: date) -> dict:
        """
        Run full collection for date d.
        """
        logger.info(f"[CollectionRunner] starting collection for {d.isoformat()}")

        if self.datastore.has_snapshot(d, "macro"):
            logger.info(f"[CollectionRunner] macro snapshot already exists for {d.isoformat()}, skipping")
            macro_data = None
        else:
            macro_data = await self._collect_macro(d)

        sector_data = await self._collect_sectors(d)
        stock_data = await self._collect_stocks(d)

        return {
            "macro": macro_data,
            "sectors": sector_data,
            "stocks": stock_data,
        }

    async def _collect_macro(self, d: date):
        """Collect macro environment data."""
        collector = MacroCollector(self.datastore, **self.common_kwargs)
        data = await collector.collect(d)
        if data:
            self.datastore.write_snapshot(d, "macro", data)
        return data

    async def _collect_sectors(self, d: date) -> dict:
        """Collect sector data (concurrent)."""
        collector = SectorCollector(
            self.datastore,
            sectors=self.sectors,
            use_pilot=self.use_pilot,
            **self.common_kwargs,
        )
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _fetch_sector(sector: str):
            async with semaphore:
                return sector, await collector.fetch_data(sector, d)

        tasks = [_fetch_sector(s) for s in collector.get_targets(d)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sector_data = {}
        for item in results:
            if isinstance(item, Exception):
                logger.error(f"[CollectionRunner] sector fetch error: {item}")
            else:
                sector, data = item
                sector_data[sector] = data
                if data:
                    self.datastore.write_snapshot(d, f"sectors/{sector}", data)

        return sector_data

    async def _collect_stocks(self, d: date) -> dict:
        """Collect stock data (concurrent)."""
        collector = StockCollector(
            self.datastore,
            stock_codes=self.stock_codes,
            **self.common_kwargs,
        )
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _fetch_stock(code: str):
            async with semaphore:
                return code, await collector.fetch_data(code, d)

        tasks = [_fetch_stock(c) for c in collector.get_targets(d)]
        if not tasks:
            logger.warning("[CollectionRunner] no stocks to collect — check stock_codes config")
            return {}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        stock_data = {}
        for item in results:
            if isinstance(item, Exception):
                logger.error(f"[CollectionRunner] stock fetch error: {item}")
            else:
                code, data = item
                stock_data[code] = data
                if data:
                    self.datastore.write_snapshot(d, f"stocks/{code}", data)

        return stock_data
