"""Tushare Pro API data fetcher with rate limiting."""

import time
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import requests
import pandas as pd

from src.config.settings import settings
from src.data.base import BaseFetcher, FetchResult


class TushareFetcher(BaseFetcher):
    """Tushare Pro API fetcher with built-in rate limiting.

    Rate limits (free tier):
    - 80 calls per minute
    - 500 calls per day

    Attributes:
        token: Tushare Pro API token
        rate_limit: Maximum calls per minute
        daily_limit: Maximum calls per day
    """

    def __init__(self):
        """Initialize Tushare fetcher with token from settings."""
        self.token = settings.tushare_token
        self.rate_limit = settings.tushare_rate_limit
        self.daily_limit = settings.tushare_daily_limit
        self.timeout = settings.request_timeout

        # Rate limiting state
        self._call_count = 0
        self._minute_start: Optional[float] = None
        self._daily_count = 0
        self._last_date: Optional[str] = None

        self.logger = self._get_logger("tushare_fetcher")

        if not self.token:
            self.logger.warning(
                "Tushare token not configured. TushareFetcher will be unavailable."
            )

    @property
    def name(self) -> str:
        return "tushare"

    @property
    def is_available(self) -> bool:
        return bool(self.token)

    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting.

        Sleeps if rate limit is reached. Resets counter each minute.
        """
        now = time.time()

        # Reset minute counter if new minute
        if self._minute_start is None or now - self._minute_start >= 60:
            self._minute_start = now
            self._call_count = 0

        # Check if rate limit reached
        if self._call_count >= self.rate_limit:
            sleep_time = 60 - (now - self._minute_start)
            if sleep_time > 0:
                self.logger.info(
                    f"Rate limit reached ({self.rate_limit}/min), waiting {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)
                self._minute_start = time.time()
                self._call_count = 0

        # Reset daily counter if new day
        today = datetime.now().strftime("%Y%m%d")
        if self._last_date != today:
            self._last_date = today
            self._daily_count = 0

        self._call_count += 1
        self._daily_count += 1

    def _call_api(self, api_name: str, params: dict = None) -> dict:
        """Call Tushare Pro API.

        Args:
            api_name: API endpoint name (e.g., "stock_basic", "daily")
            params: API parameters

        Returns:
            API response as dict

        Raises:
            requests.RequestException: On HTTP error
            ValueError: On API error response
        """
        self._check_rate_limit()

        url = "http://api.tushare.pro"
        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params or {},
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()

        result = response.json()

        if result.get("code") != 0:
            raise ValueError(
                f"Tushare API error: {result.get('msg', 'Unknown error')}"
            )

        return result

    def get_stock_list(self) -> FetchResult:
        """Fetch stock list from Tushare.

        Returns:
            FetchResult with stock list DataFrame
        """
        try:
            self.logger.info("Fetching stock list from Tushare")

            result = self._call_api("stock_basic", {"exchange": "", "list_status": "L"})

            data = result.get("data", {})
            items = data.get("items", [])
            fields = data.get("fields", [])

            if not items:
                self.logger.warning("Tushare returned empty stock list")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            df = pd.DataFrame(items, columns=fields)

            # Rename to standard columns
            rename_map = {}
            if "ts_code" in df.columns:
                rename_map["ts_code"] = "ts_code"
            if "symbol" in df.columns:
                rename_map["symbol"] = "ts_code"
            if "name" in df.columns:
                rename_map["name"] = "name"
            if "industry" in df.columns:
                rename_map["industry"] = "industry"
            if "list_date" in df.columns:
                rename_map["list_date"] = "listed_date"

            df = df.rename(columns=rename_map)

            self.logger.info(f"Fetched {len(df)} stocks from Tushare")

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
        """Fetch daily market data from Tushare.

        Args:
            ts_code: Stock code (e.g., "000001.SZ")
            days: Number of days to fetch

        Returns:
            FetchResult with daily data DataFrame
        """
        try:
            self.logger.info(f"Fetching daily data for {ts_code} ({days} days)")

            # Calculate date range
            end_date = datetime.now()
            start_date = datetime.now()

            # Fetch more data to account for non-trading days
            result = self._call_api(
                "daily",
                {
                    "ts_code": ts_code,
                    "start_date": start_date.strftime("%Y%m%d"),
                    "end_date": end_date.strftime("%Y%m%d"),
                },
            )

            data = result.get("data", {})
            items = data.get("items", [])
            fields = data.get("fields", [])

            if not items:
                # Try historical data if today has no data
                result = self._call_api(
                    "daily",
                    {
                        "ts_code": ts_code,
                        "start_date": (datetime.now().replace(day=1)).strftime("%Y%m%d"),
                        "end_date": end_date.strftime("%Y%m%d"),
                    },
                )
                data = result.get("data", {})
                items = data.get("items", [])
                fields = data.get("fields", [])

            if not items:
                self.logger.warning(f"No daily data for {ts_code}")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            df = pd.DataFrame(items, columns=fields)

            # Rename to standard columns
            rename_map = {
                "ts_code": "ts_code",
                "trade_date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "vol": "volume",
                "amount": "amount",
            }
            df = df.rename(columns=rename_map)

            # Convert types
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Take most recent 'days' records
            df = df.head(days)

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
        """Fetch limit up/down stocks from Tushare.

        Args:
            trade_date: Trading date (YYYYMMDD format)

        Returns:
            FetchResult with limit stocks DataFrame
        """
        try:
            self.logger.info(f"Fetching limit list for {trade_date}")

            result = self._call_api("limit_list", {"trade_date": trade_date})

            data = result.get("data", {})
            items = data.get("items", [])
            fields = data.get("fields", [])

            if not items:
                self.logger.info(f"No limit stocks for {trade_date}")
                return FetchResult(
                    success=True,
                    data=pd.DataFrame(),
                    source=self.name,
                    metadata={"count": 0},
                )

            df = pd.DataFrame(items, columns=fields)

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

    async def fetch_sector_constituents(self, sector_id: str) -> List[dict]:
        """Fetch sector constituents from Tushare.

        Uses index_member API for industry indices.

        Args:
            sector_id: Sector/index code (e.g., "881100.WI" for Wind industry index)

        Returns:
            List of dicts with stock_code, sector_id, sector_name, is_primary
        """
        try:
            self.logger.info(f"Fetching constituents for sector {sector_id}")

            # Use index_member API
            result = self._call_api("index_member", {"index_code": sector_id})

            data = result.get("data", {})
            items = data.get("items", [])
            fields = data.get("fields", [])

            if not items:
                self.logger.warning(f"No constituents found for sector {sector_id}")
                return []

            df = pd.DataFrame(items, columns=fields)

            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "stock_code": row.get("ts_code", ""),
                        "sector_id": sector_id,
                        "sector_type": "industry",
                        "sector_name": row.get("index_name", ""),
                        "affiliation_strength": Decimal("1.0"),
                        "is_primary": True,  # Index constituent = primary
                    }
                )

            self.logger.info(f"Fetched {len(records)} constituents for sector {sector_id}")
            return records

        except Exception as e:
            self.logger.error(f"Failed to fetch sector constituents: {e}")
            return []

    async def fetch_concept_constituents(self, concept_id: str) -> List[dict]:
        """Fetch concept sector constituents from Tushare.

        Uses concept_detail API for concept sectors.

        Args:
            concept_id: Concept ID (e.g., "BK0001" for concept)

        Returns:
            List of dicts with stock_code, sector_id, sector_type, sector_name
        """
        try:
            self.logger.info(f"Fetching constituents for concept {concept_id}")

            # Use concept_detail API
            result = self._call_api("concept_detail", {"concept_id": concept_id})

            data = result.get("data", {})
            items = data.get("items", [])
            fields = data.get("fields", [])

            if not items:
                self.logger.warning(f"No constituents found for concept {concept_id}")
                return []

            df = pd.DataFrame(items, columns=fields)

            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "stock_code": row.get("ts_code", ""),
                        "sector_id": concept_id,
                        "sector_type": "concept",
                        "sector_name": row.get("concept_name", ""),
                        "affiliation_strength": Decimal("0.8"),  # Concept = secondary affiliation
                        "is_primary": False,  # Concept = secondary
                    }
                )

            self.logger.info(f"Fetched {len(records)} constituents for concept {concept_id}")
            return records

        except Exception as e:
            self.logger.error(f"Failed to fetch concept constituents: {e}")
            return []
