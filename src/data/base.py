"""Base classes for data fetchers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import logging
import pandas as pd


@dataclass
class FetchResult:
    """Result from a data fetcher operation.

    Attributes:
        success: Whether the fetch operation succeeded
        data: Fetched data as DataFrame (empty DataFrame on failure)
        error: Error message if operation failed, None otherwise
        source: Name of the data source (e.g., "tushare", "akshare")
        metadata: Additional metadata from the fetch operation
    """

    success: bool
    data: Optional[pd.DataFrame] = None
    error: Optional[str] = None
    source: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.data is None:
            self.data = pd.DataFrame()


class BaseFetcher(ABC):
    """Abstract base class for all data fetchers.

    All fetchers must implement the same interface to enable failover logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this fetcher (e.g., 'tushare', 'akshare')."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if this fetcher is available and ready to use."""
        return True

    @abstractmethod
    def get_stock_list(self) -> FetchResult:
        """Fetch the list of all stocks.

        Returns:
            FetchResult with DataFrame containing columns:
            - ts_code: Stock code (e.g., "000001.SZ")
            - name: Stock name
            - industry: Industry classification
            - listed_date: IPO date
        """
        pass

    @abstractmethod
    def get_daily_data(
        self, ts_code: str, days: int = 1
    ) -> FetchResult:
        """Fetch daily market data for a stock.

        Args:
            ts_code: Stock code (e.g., "000001.SZ")
            days: Number of days to fetch (default: 1, most recent)

        Returns:
            FetchResult with DataFrame containing columns:
            - ts_code: Stock code
            - trade_date: Trading date
            - open: Opening price
            - high: Highest price
            - low: Lowest price
            - close: Closing price
            - volume: Trading volume
            - amount: Trading amount
        """
        pass

    @abstractmethod
    def get_limit_list(self, trade_date: str) -> FetchResult:
        """Fetch limit up/down stocks for a trading date.

        Args:
            trade_date: Trading date (YYYYMMDD format)

        Returns:
            FetchResult with DataFrame containing limit up/down stocks
        """
        pass

    def _get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for this fetcher."""
        logger = logging.getLogger(name)
        logger.propagate = True
        return logger
