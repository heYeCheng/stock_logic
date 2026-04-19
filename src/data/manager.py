"""Data fetcher manager with priority-based failover logic."""

import logging
from typing import List, Tuple
import pandas as pd

from src.data.base import BaseFetcher, FetchResult
from src.data.tushare_fetcher import TushareFetcher
from src.data.akshare_fetcher import AkshareFetcher
from src.data.efinance_fetcher import EfinanceFetcher


class DataFetcherManager:
    """Manager for data fetchers with automatic failover.

    Failover priority: Tushare -> Akshare -> Efinance

    Tushare is primary (requires token, rate limited).
    Akshare and Efinance are fallbacks (no token required).
    """

    def __init__(self):
        """Initialize fetcher manager with all data sources."""
        self.logger = self._get_logger("data_manager")

        # Initialize fetchers
        self.tushare = TushareFetcher()
        self.akshare = AkshareFetcher()
        self.efinance = EfinanceFetcher()

        # Priority-ordered list (lower priority number = higher priority)
        self.fetchers: List[Tuple[BaseFetcher, int]] = [
            (self.tushare, 1),
            (self.akshare, 2),
            (self.efinance, 3),
        ]

        self.logger.info(
            f"DataFetcherManager initialized with {len(self.fetchers)} fetchers"
        )

    def _get_logger(self, name: str) -> logging.Logger:
        """Get logger instance."""
        logger = logging.getLogger(name)
        logger.propagate = True
        return logger

    def get_stock_list(self) -> pd.DataFrame:
        """Fetch stock list with failover.

        Returns:
            DataFrame with stock list, or empty DataFrame on failure.
        """
        errors = []

        for fetcher, priority in self.fetchers:
            if not fetcher.is_available:
                self.logger.debug(f"Fetcher {fetcher.name} not available, skipping")
                continue

            self.logger.info(f"Attempting get_stock_list with {fetcher.name}")

            try:
                result = fetcher.get_stock_list()

                if result.success and not result.data.empty:
                    self.logger.info(
                        f"Successfully fetched stock list from {fetcher.name}: {len(result.data)} stocks"
                    )
                    return result.data

                if result.error:
                    errors.append(f"{fetcher.name}: {result.error}")
                    self.logger.warning(f"Fetcher {fetcher.name} failed: {result.error}")

            except Exception as e:
                errors.append(f"{fetcher.name}: {str(e)}")
                self.logger.error(f"Fetcher {fetcher.name} exception: {e}")

        # All fetchers failed
        if errors:
            self.logger.error(f"All fetchers failed for get_stock_list: {errors}")
        else:
            self.logger.warning("All fetchers returned empty stock list")

        return pd.DataFrame()

    def get_daily_data(
        self, ts_code: str, days: int = 1
    ) -> Tuple[pd.DataFrame, str]:
        """Fetch daily data with failover.

        Args:
            ts_code: Stock code
            days: Number of days to fetch

        Returns:
            Tuple of (DataFrame, source_name).
            Empty DataFrame and "none" source on failure.
        """
        errors = []

        for fetcher, priority in self.fetchers:
            if not fetcher.is_available:
                self.logger.debug(f"Fetcher {fetcher.name} not available, skipping")
                continue

            self.logger.info(
                f"Attempting get_daily_data for {ts_code} with {fetcher.name}"
            )

            try:
                result = fetcher.get_daily_data(ts_code, days)

                if result.success and not result.data.empty:
                    self.logger.info(
                        f"Successfully fetched {len(result.data)} records from {fetcher.name}"
                    )
                    return result.data, fetcher.name

                if result.error:
                    errors.append(f"{fetcher.name}: {result.error}")
                    self.logger.warning(
                        f"Fetcher {fetcher.name} failed for {ts_code}: {result.error}"
                    )

            except Exception as e:
                errors.append(f"{fetcher.name}: {str(e)}")
                self.logger.error(f"Fetcher {fetcher.name} exception for {ts_code}: {e}")

        # All fetchers failed
        if errors:
            self.logger.error(f"All fetchers failed for {ts_code}: {errors}")
        else:
            self.logger.warning(f"All fetchers returned empty data for {ts_code}")

        return pd.DataFrame(), "none"

    def get_limit_list(self, trade_date: str) -> pd.DataFrame:
        """Fetch limit up/down stocks with failover.

        Args:
            trade_date: Trading date (YYYYMMDD format)

        Returns:
            DataFrame with limit stocks, or empty DataFrame on failure.
        """
        errors = []

        for fetcher, priority in self.fetchers:
            if not fetcher.is_available:
                self.logger.debug(f"Fetcher {fetcher.name} not available, skipping")
                continue

            self.logger.info(f"Attempting get_limit_list with {fetcher.name}")

            try:
                result = fetcher.get_limit_list(trade_date)

                if result.success and not result.data.empty:
                    self.logger.info(
                        f"Successfully fetched limit list from {fetcher.name}: {len(result.data)} stocks"
                    )
                    return result.data

                if result.error:
                    errors.append(f"{fetcher.name}: {result.error}")
                    self.logger.warning(f"Fetcher {fetcher.name} failed: {result.error}")

            except Exception as e:
                errors.append(f"{fetcher.name}: {str(e)}")
                self.logger.error(f"Fetcher {fetcher.name} exception: {e}")

        # All fetchers failed
        if errors:
            self.logger.error(f"All fetchers failed for get_limit_list: {errors}")
        else:
            self.logger.warning("All fetchers returned empty limit list")

        return pd.DataFrame()
