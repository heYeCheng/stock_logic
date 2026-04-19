"""Akshare fetcher - free data source without token requirement."""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from src.data.base import BaseFetcher, FetchResult


class AkshareFetcher(BaseFetcher):
    """Akshare data fetcher using East Money web scraping.

    Features:
    - No token required
    - Free to use
    - Covers A-shares, ETFs, HK stocks

    Note: This is a simplified Phase 1 implementation.
    Full implementation includes rate limiting, circuit breakers,
    and multi-source fallback (Sina, Tencent) as shown in old/data_provider/akshare_fetcher.py.
    """

    def __init__(self):
        """Initialize Akshare fetcher."""
        self.logger = self._get_logger("akshare_fetcher")

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def is_available(self) -> bool:
        return True

    def get_stock_list(self) -> FetchResult:
        """Fetch stock list from Akshare.

        Returns:
            FetchResult with DataFrame containing:
            - ts_code: Stock code
            - name: Stock name
            - industry: Industry (if available)
        """
        try:
            import akshare as ak

            self.logger.info("Fetching stock list from Akshare")

            # Use ak.stock_info_a_code_name() for A-share list
            df = ak.stock_info_a_code_name()

            if df is None or df.empty:
                self.logger.warning("Akshare returned empty stock list")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            # Standardize columns
            rename_map = {}
            if "code" in df.columns:
                rename_map["code"] = "ts_code"
            if "name" in df.columns:
                rename_map["name"] = "name"

            df = df.rename(columns=rename_map)

            self.logger.info(f"Fetched {len(df)} stocks from Akshare")

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
        """Fetch daily market data from Akshare.

        Args:
            ts_code: Stock code (e.g., "600519")
            days: Number of days to fetch

        Returns:
            FetchResult with OHLCV data
        """
        try:
            import akshare as ak

            self.logger.info(f"Fetching daily data for {ts_code} ({days} days)")

            # Calculate date range (get extra days to account for non-trading days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days * 3)

            # Use ak.stock_zh_a_hist() for A-share historical data
            df = ak.stock_zh_a_hist(
                symbol=ts_code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",  # Forward adjusted for splits
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
            import akshare as ak

            self.logger.info(f"Fetching limit list for {trade_date}")

            # Use ak.stock_limit_board_em() for limit up/down data
            df = ak.stock_limit_board_em(
                start_date=trade_date,
                end_date=trade_date,
            )

            if df is None or df.empty:
                self.logger.info(f"No limit stocks for {trade_date}")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            self.logger.info(f"Fetched {len(df)} limit stocks")

            return FetchResult(
                success=True,
                data=df,
                source=self.name,
                metadata={"count": len(df)},
            )

        except Exception as e:
            self.logger.error(f"Failed to fetch limit list: {e}")
            return FetchResult(
                success=False,
                error=str(e),
                source=self.name,
            )
