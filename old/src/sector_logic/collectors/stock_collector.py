# -*- coding: utf-8 -*-
"""
StockCollector: fetches stock-level data using real DSA infrastructure.

Sources:
  - DataFetcherManager.get_daily_data(): OHLCV with MA indicators
  - DataFetcherManager.get_realtime_quote(): PE/PB/market cap/turnover
  - fundamental_adapter.get_valuation(): PE/PB/ROE
  - fundamental_adapter.get_capital_flow(): 主力净流入
  - fundamental_adapter.get_growth(): 营收增速/净利增速
  - efinance.get_belong_board(): 个股所属板块
  - search_service: 个股相关新闻
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .base import AsyncCollector

logger = logging.getLogger(__name__)


class StockCollector(AsyncCollector):
    """Collects stock-level data for a given date using real DSA infrastructure."""

    def __init__(
        self,
        datastore,
        stock_codes: Optional[List[str]] = None,
        top_n: int = 200,
        include_watchlist: bool = True,
        **kwargs,
    ):
        super().__init__(datastore, **kwargs)
        self.top_n = top_n
        self.include_watchlist = include_watchlist
        self._stock_codes = stock_codes
        self._watchlist = self._load_watchlist() if include_watchlist else []

    def _load_watchlist(self) -> List[str]:
        """Load user watchlist stocks from config or file."""
        try:
            from src.config import get_config
            config = get_config()
            watchlist = getattr(config, "stock_watchlist", None)
            if watchlist:
                return watchlist.split(",") if isinstance(watchlist, str) else watchlist
        except Exception:
            pass
        return []

    async def fetch_data(self, stock_code: str, d: date) -> Optional[Dict[str, Any]]:
        """
        Fetch all stock-level data for one stock.
        """
        result = {
            "stock_code": stock_code,
            "date": d.isoformat(),
            "stock_name": "",
            "ohlcv": {},
            "realtime_quote": {},
            "fundamentals": {},
            "capital_flow": {},
            "belong_board": [],
            "news": [],
        }

        # 1. OHLCV from DataFetcherManager
        result["ohlcv"] = await self._fetch_ohlcv(stock_code, d)

        # 2. Realtime quote (PE/PB/market cap)
        result["realtime_quote"] = await self._fetch_realtime_quote(stock_code)

        # 3. Fundamentals (valuation + growth)
        result["fundamentals"] = await self._fetch_fundamentals(stock_code)

        # 4. Capital flow
        result["capital_flow"] = await self._fetch_capital_flow(stock_code)

        # 5. Sector mapping
        result["belong_board"] = await self._fetch_belong_board(stock_code)

        # 6. News
        result["news"] = await self._search_stock_news(stock_code, d)

        return result

    async def _fetch_ohlcv(self, stock_code: str, d: date) -> Dict[str, Any]:
        """Fetch OHLCV + MA indicators from DataFetcherManager."""
        try:
            from data_provider.base import DataFetcherManager
            import pandas as pd

            dfm = DataFetcherManager()
            # Get 30 days of daily data for technical analysis
            df = dfm.get_daily_data(
                stock_code=stock_code,
                start_date=(d - pd.Timedelta(days=60)).strftime("%Y-%m-%d"),
                end_date=d.strftime("%Y-%m-%d"),
                days=30,
            )

            if df is not None and not df.empty:
                # Get target date data
                day_data = df[df["date"] == d.strftime("%Y-%m-%d")]
                if not day_data.empty:
                    row = day_data.iloc[0]
                    return {
                        "open": float(row.get("open", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "close": float(row.get("close", 0)),
                        "volume": float(row.get("volume", 0)),
                        "amount": float(row.get("amount", 0)),
                        "pct_chg": float(row.get("pct_chg", 0)),
                        "ma5": float(row.get("ma5", 0)),
                        "ma10": float(row.get("ma10", 0)),
                        "ma20": float(row.get("ma20", 0)),
                        "volume_ratio": float(row.get("volume_ratio", 0)),
                        "source": "dfm",
                        "history_5d": df.tail(5).to_dict(orient="records"),
                        "history_20d": df.tail(20).to_dict(orient="records"),
                    }

            logger.warning(f"[StockCollector] no OHLCV data for {stock_code} on {d.isoformat()}")
            return {"source": "dfm", "available": False}

        except Exception as e:
            logger.warning(f"[StockCollector] OHLCV for {stock_code} failed: {e}")
            return {"source": "dfm", "error": str(e)}

    async def _fetch_realtime_quote(self, stock_code: str) -> Dict[str, Any]:
        """Fetch PE/PB/market cap from DataFetcherManager."""
        try:
            from data_provider.base import DataFetcherManager

            dfm = DataFetcherManager()
            quote = dfm.get_realtime_quote(stock_code)

            if quote:
                return {
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "volume": quote.volume,
                    "amount": quote.amount,
                    "pe_ratio": quote.pe_ratio,
                    "pb_ratio": quote.pb_ratio,
                    "total_mv": quote.total_mv,
                    "turnover_rate": quote.turnover_rate,
                    "source": "dfm",
                }

            return {"source": "dfm", "available": False}

        except Exception as e:
            logger.warning(f"[StockCollector] realtime quote for {stock_code} failed: {e}")
            return {"source": "dfm", "error": str(e)}

    async def _fetch_fundamentals(self, stock_code: str) -> Dict[str, Any]:
        """Fetch valuation + growth from fundamental_adapter."""
        result = {}

        try:
            from data_provider.fundamental_adapter import AkshareFundamentalAdapter

            adapter = AkshareFundamentalAdapter()

            # Valuation: PE/PB/ROE
            valuation = adapter.get_valuation(stock_code)
            if valuation and valuation.get("status") != "not_supported":
                result["valuation"] = {
                    "pe": valuation.get("pe", 0),
                    "pb": valuation.get("pb", 0),
                    "roe": valuation.get("roe", 0),
                    "pe_percentile": valuation.get("pe_percentile"),
                    "source": valuation.get("source_chain", []),
                }

            # Growth: revenue_yoy, net_profit_yoy
            growth = adapter.get_growth(stock_code)
            if growth and growth.get("status") != "not_supported":
                result["growth"] = {
                    "revenue_yoy": growth.get("revenue_yoy"),
                    "net_profit_yoy": growth.get("net_profit_yoy"),
                    "gross_margin": growth.get("gross_margin"),
                    "source": growth.get("source_chain", []),
                }

        except Exception as e:
            logger.warning(f"[StockCollector] fundamentals for {stock_code} failed: {e}")

        return result if result else {"source": "fundamental_adapter", "available": False}

    async def _fetch_capital_flow(self, stock_code: str) -> Dict[str, Any]:
        """Fetch capital flow from fundamental_adapter."""
        try:
            from data_provider.fundamental_adapter import AkshareFundamentalAdapter

            adapter = AkshareFundamentalAdapter()
            flow = adapter.get_capital_flow(stock_code)

            if flow and flow.get("status") != "not_supported":
                return {
                    "main_net_inflow": flow.get("stock_flow", {}).get("main_net_inflow"),
                    "inflow_5d": flow.get("stock_flow", {}).get("inflow_5d"),
                    "inflow_10d": flow.get("stock_flow", {}).get("inflow_10d"),
                    "source": flow.get("source_chain", []),
                }

            return {"source": "fundamental_adapter", "available": False}

        except Exception as e:
            logger.warning(f"[StockCollector] capital flow for {stock_code} failed: {e}")
            return {"source": "fundamental_adapter", "error": str(e)}

    async def _fetch_belong_board(self, stock_code: str) -> List[Dict[str, Any]]:
        """Fetch stock sector mapping from efinance."""
        try:
            from data_provider.base import DataFetcherManager

            dfm = DataFetcherManager()
            boards = dfm.get_belong_boards(stock_code)

            return [
                {
                    "board_name": b.get("board_name") or b.get("板块名称") or "",
                    "board_code": b.get("board_code") or b.get("板块代码") or "",
                    "board_type": b.get("board_type") or b.get("板块类型") or "",
                }
                for b in boards
            ]

        except Exception as e:
            logger.warning(f"[StockCollector] belong board for {stock_code} failed: {e}")
            return []

    async def _search_stock_news(self, stock_code: str, d: date) -> List[Dict[str, Any]]:
        """Search recent news for a stock using existing search_service."""
        try:
            from data_provider.base import DataFetcherManager
            from src.search_service import SearchService

            dfm = DataFetcherManager()
            stock_name = dfm.get_stock_name(stock_code, allow_realtime=True) or stock_code

            search_service = SearchService()
            results = search_service.search_stock_news(
                stock_code=stock_code,
                stock_name=stock_name,
                max_results=10,
            )

            news_items = []
            if results and results.items:
                for item in results.items[:10]:
                    news_items.append({
                        "title": item.title or "",
                        "snippet": item.snippet or "",
                        "url": item.url or "",
                        "source": item.source or "unknown",
                        "published_date": item.published_date.isoformat() if item.published_date else "",
                    })

            return news_items

        except Exception as e:
            logger.warning(f"[StockCollector] news search for {stock_code} failed: {e}")
            return []

    def get_targets(self, d: date) -> List[str]:
        """Get list of stock codes to collect."""
        if self._stock_codes:
            return self._stock_codes

        # Try to get top200 by trading volume from DataFetcherManager
        try:
            from data_provider.base import DataFetcherManager

            dfm = DataFetcherManager()
            stock_list = dfm.get_stock_list()
            if stock_list is not None and not stock_list.empty:
                # Sort by amount (成交额) — use realtime quote to get amounts
                # For simplicity, use stock list as-is for now
                # In production, filter by market cap + volume
                codes = stock_list["code"].head(self.top_n).tolist()
                return codes + self._watchlist

        except Exception as e:
            logger.warning(f"[StockCollector] get_stock_list failed: {e}")

        return self._watchlist

    async def collect_all(self, d: date) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Collect data for all stocks with concurrency limit.
        """
        import asyncio

        targets = self.get_targets(d)
        results = {}
        semaphore = asyncio.Semaphore(self.max_concurrency if hasattr(self, "max_concurrency") else 10)

        async def _fetch_with_limit(code: str):
            async with semaphore:
                return code, await self.fetch_data(code, d)

        tasks = [_fetch_with_limit(c) for c in targets]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        for item in fetched:
            if isinstance(item, Exception):
                logger.error(f"[StockCollector] fetch error: {item}")
            else:
                code, data = item
                results[code] = data

        return results
