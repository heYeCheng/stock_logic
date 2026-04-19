"""Efinance fetcher - free data source without token requirement."""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from src.data.base import BaseFetcher, FetchResult


class EfinanceFetcher(BaseFetcher):
    """Efinance data fetcher using East Money web scraping.

    Features:
    - No token required
    - Free to use
    - Completely open source

    Note: This is a simplified Phase 1 implementation.
    Full implementation includes rate limiting and circuit breakers.
    """

    def __init__(self):
        """Initialize Efinance fetcher."""
        self.logger = self._get_logger("efinance_fetcher")

    @property
    def name(self) -> str:
        return "efinance"

    @property
    def is_available(self) -> bool:
        return True

    def get_stock_list(self) -> FetchResult:
        """Fetch stock list from Efinance.

        Returns:
            FetchResult with DataFrame containing stock list
        """
        try:
            import efinance as ef

            self.logger.info("Fetching stock list from Efinance")

            # Get all A-share stock codes
            df = ef.stock.get_all_stock_code()

            if df is None or df.empty:
                self.logger.warning("Efinance returned empty stock list")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            # Standardize columns
            rename_map = {}
            if "代码" in df.columns:
                rename_map["代码"] = "ts_code"
            if "名称" in df.columns:
                rename_map["名称"] = "name"
            if "行业" in df.columns:
                rename_map["行业"] = "industry"

            df = df.rename(columns=rename_map)

            self.logger.info(f"Fetched {len(df)} stocks from Efinance")

            return FetchResult(
                success=True,
                data=df,
                source=self.name,
                metadata={"count": len(df)},
            )

        except Exception as e:
            self.logger.error(f"Failed to fetch stock list: {e}")
            return FetchResult(
                success=False,
                error=str(e),
                source=self.name,
            )

    def get_daily_data(self, ts_code: str, days: int = 1) -> FetchResult:
        """Fetch daily market data from Efinance.

        Args:
            ts_code: Stock code (e.g., "600519")
            days: Number of days to fetch

        Returns:
            FetchResult with OHLCV data
        """
        try:
            import efinance as ef

            self.logger.info(f"Fetching daily data for {ts_code} ({days} days)")

            # Get recent historical data
            df = ef.stock.get_quote_history(
                ts_code,
                count=days * 2,  # Get extra to account for non-trading days
            )

            if df is None or df.empty:
                self.logger.warning(f"No daily data for {ts_code}")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            # Standardize columns
            rename_map = {
                "日期": "trade_date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
            }
            df = df.rename(columns=rename_map)

            # Convert types
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Take most recent 'days' records
            df = df.tail(days).reset_index(drop=True)

            self.logger.info(f"Fetched {len(df)} records for {ts_code}")

            return FetchResult(
                success=True,
                data=df,
                source=self.name,
                metadata={"count": len(df)},
            )

        except Exception as e:
            self.logger.error(f"Failed to fetch daily data for {ts_code}: {e}")
            return FetchResult(
                success=False,
                error=str(e),
                source=self.name,
            )

    def get_limit_list(self, trade_date: str) -> FetchResult:
        """Fetch limit up/down stocks for a trading date.

        Args:
            trade_date: Trading date (YYYYMMDD format)

        Returns:
            FetchResult with limit stocks DataFrame
        """
        try:
            import efinance as ef

            self.logger.info(f"Fetching limit list for {trade_date}")

            # Efinance doesn't have a direct limit list API
            # Return empty result for Phase 1
            self.logger.info("Limit list not available in Efinance (Phase 1)")

            return FetchResult(
                success=True,
                data=pd.DataFrame(),
                source=self.name,
                metadata={"count": 0},
            )

        except Exception as e:
            self.logger.error(f"Failed to fetch limit list: {e}")
            return FetchResult(
                success=False,
                error=str(e),
                source=self.name,
            )
