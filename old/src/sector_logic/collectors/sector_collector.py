# -*- coding: utf-8 -*-
"""
SectorCollector: fetches sector-level data using efinance (直连，无需代理).

Primary source: efinance (东方财富数据，直连)
  - get_realtime_quotes(['行业板块']): 板块涨跌排行
  - get_quote_history(sector_name): 板块指数历史 K 线
  - get_today_bill(BK_code): 板块当日资金流向
  - get_history_bill(BK_code): 板块历史资金流向

注意：
  - efinance 通过 eastmoney_patch 直连，不使用代理
  - 需要确保代理环境变量已清除或被 patch 覆盖
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import AsyncCollector

logger = logging.getLogger(__name__)


# Pilot sector list — the 4 sectors to validate first
# name: 显示名称
# efinance_name: 东方财富板块名（用于 get_quote_history / get_realtime_quotes）
PILOT_SECTORS = [
    {"name": "光伏", "efinance_name": "光伏设备"},
    {"name": "半导体", "efinance_name": "半导体"},
    {"name": "CPO/光通信模块", "efinance_name": "光通信设备"},
    {"name": "AI/算力", "efinance_name": "人工智能"},
]

# Full sector list (expand later)
CORE_SECTORS = [
    {"name": "光伏", "efinance_name": "光伏设备"},
    {"name": "半导体", "efinance_name": "半导体"},
    {"name": "CPO/光通信模块", "efinance_name": "光通信设备"},
    {"name": "AI/算力", "efinance_name": "人工智能"},
    {"name": "新能源车", "efinance_name": "新能源车"},
    {"name": "医药", "efinance_name": "化学制药"},
    {"name": "消费", "efinance_name": "零售"},
    {"name": "黄金", "efinance_name": "贵金属"},
    {"name": "银行", "efinance_name": "银行"},
    {"name": "地产", "efinance_name": "房地产开发"},
    {"name": "猪周期/养殖", "efinance_name": "养殖业"},
    {"name": "面板/显示", "efinance_name": "光学光电子"},
    {"name": "储能/电池", "efinance_name": "电池"},
    {"name": "军工", "efinance_name": "军工"},
    {"name": "白酒", "efinance_name": "白酒"},
    {"name": "钢铁", "efinance_name": "钢铁"},
    {"name": "煤炭", "efinance_name": "煤炭"},
    {"name": "化工", "efinance_name": "化学制品"},
    {"name": "风电", "efinance_name": "风电设备"},
]


class SectorCollector(AsyncCollector):
    """Collects sector-level data for a given date using efinance."""

    def __init__(self, datastore, sectors: Optional[List[str]] = None, use_pilot: bool = False, **kwargs):
        super().__init__(datastore, **kwargs)
        sector_list = PILOT_SECTORS if use_pilot else CORE_SECTORS
        self.sectors = sectors or [s["name"] for s in sector_list]
        self._sector_map = {s["name"]: s for s in CORE_SECTORS}
        self._bk_cache: Dict[str, str] = {}  # sector_name -> BK code
        self._ef_imported = False

    def _ensure_efinance(self):
        """Ensure efinance is imported and patch is applied."""
        if not self._ef_imported:
            from patch.eastmoney_patch import eastmoney_patch
            eastmoney_patch()
            self._ef_imported = True

    def _resolve_bk_code(self, efinance_name: str) -> Optional[str]:
        """Resolve sector name to BK code from cache or realtime quotes."""
        if efinance_name in self._bk_cache:
            return self._bk_cache[efinance_name]

        self._ensure_efinance()
        import efinance as ef

        try:
            df = ef.stock.get_realtime_quotes(['行业板块'])
            if df is not None and not df.empty:
                name_col = '股票名称' if '股票名称' in df.columns else 'name'
                code_col = '股票代码' if '股票代码' in df.columns else 'code'
                if name_col in df.columns and code_col in df.columns:
                    for _, row in df.iterrows():
                        self._bk_cache[row[name_col]] = row[code_col]
                    logger.info(f"[SectorCollector] cached {len(self._bk_cache)} BK codes")
                    return self._bk_cache.get(efinance_name)
        except Exception as e:
            logger.warning(f"[SectorCollector] BK code resolution failed: {e}")

        return None

    async def fetch_data(self, sector_name: str, d: date) -> Optional[Dict[str, Any]]:
        """
        Fetch all sector-level data for one sector.

        Steps:
        1. Get sector index OHLCV from efinance (get_quote_history)
        2. Get sector capital flow from efinance (get_today_bill / get_history_bill)
        3. Search recent news for this sector
        """
        sector_info = self._sector_map.get(sector_name, {"name": sector_name, "efinance_name": sector_name})

        result = {
            "sector": sector_name,
            "sector_code": sector_info.get("efinance_name", ""),
            "date": d.isoformat(),
            "sector_index": {},
            "capital_flow": {},
            "news_items": [],
            "policy_signals": [],
        }

        # 1. Sector index OHLCV from efinance
        result["sector_index"] = await self._fetch_sector_index_ohlcv(sector_info, d)

        # 2. Capital flow from efinance
        result["capital_flow"] = await self._fetch_sector_capital_flow(sector_info, d)

        # 3. News search
        result["news_items"] = await self._search_sector_news(sector_name, d)

        return result

    async def _fetch_sector_index_ohlcv(self, sector_info: Dict, d: date) -> Dict[str, Any]:
        """
        Fetch sector index OHLCV from efinance get_quote_history.

        获取板块指数历史 K 线数据，包含 OHLCV 和涨跌幅。
        """
        efinance_name = sector_info.get("efinance_name", sector_info.get("name"))
        self._ensure_efinance()

        try:
            import efinance as ef

            date_str = d.strftime("%Y%m%d")
            start = (d - pd.Timedelta(days=60)).strftime("%Y%m%d")

            # klt=101 (日线), fqt=1 (前复权)
            df = ef.stock.get_quote_history(efinance_name, beg=start, end=date_str, klt=101, fqt=1)

            if df is not None and not df.empty:
                date_col = '日期' if '日期' in df.columns else 'date'
                if date_col in df.columns:
                    # 尝试匹配指定日期
                    target_date = d.strftime("%Y-%m-%d")
                    day_data = df[df[date_col] == target_date]
                    if not day_data.empty:
                        row = day_data.iloc[0]
                        return {
                            "open": float(row.get("开盘", 0)),
                            "high": float(row.get("最高", 0)),
                            "low": float(row.get("最低", 0)),
                            "close": float(row.get("收盘", 0)),
                            "volume": float(row.get("成交量", 0)),
                            "amount": float(row.get("成交额", 0)),
                            "pct_chg": float(row.get("涨跌幅", 0)),
                            "source": "efinance",
                            "history_5d": df.tail(5).to_dict(orient="records"),
                            "history_20d": df.tail(20).to_dict(orient="records"),
                        }
                    else:
                        # 使用最新可用数据
                        latest = df.iloc[-1]
                        return {
                            "open": float(latest.get("开盘", 0)),
                            "high": float(latest.get("最高", 0)),
                            "low": float(latest.get("最低", 0)),
                            "close": float(latest.get("收盘", 0)),
                            "volume": float(latest.get("成交量", 0)),
                            "amount": float(latest.get("成交额", 0)),
                            "pct_chg": float(latest.get("涨跌幅", 0)),
                            "source": "efinance",
                            "note": f"no data for {d.isoformat()}, using latest available",
                        }

            logger.warning(f"[SectorCollector] no index data for {efinance_name} on {d.isoformat()}")
            return {"source": "efinance", "available": False}

        except Exception as e:
            logger.warning(f"[SectorCollector] efinance sector index for {efinance_name} failed: {e}")
            return {"source": "efinance", "error": str(e)}

    async def _fetch_sector_capital_flow(self, sector_info: Dict, d: date) -> Dict[str, Any]:
        """
        Fetch sector capital flow from efinance get_today_bill / get_history_bill.

        需要先获取板块的 BK 代码（如 BK1031）。
        """
        efinance_name = sector_info.get("efinance_name", sector_info.get("name"))
        self._ensure_efinance()

        try:
            # 获取 BK 代码
            bk_code = self._resolve_bk_code(efinance_name)
            if not bk_code:
                return {"source": "efinance", "available": False, "note": f"could not resolve BK code for {efinance_name}"}

            import efinance as ef

            # Try today's bill first
            today_bill = ef.stock.get_today_bill(bk_code)
            if today_bill is not None and not today_bill.empty:
                latest = today_bill.iloc[-1]
                return {
                    "net_flow": float(latest.get("主力净流入", 0) or 0),
                    "big_inflow": float(latest.get("大单净流入", 0) or 0),
                    "super_inflow": float(latest.get("超大单净流入", 0) or 0),
                    "small_inflow": float(latest.get("小单净流入", 0) or 0),
                    "medium_inflow": float(latest.get("中单净流入", 0) or 0),
                    "source": "efinance",
                    "type": "today_bill",
                }

            # Fallback: history bill
            hist_bill = ef.stock.get_history_bill(bk_code)
            if hist_bill is not None and not hist_bill.empty:
                latest = hist_bill.iloc[-1]
                return {
                    "net_flow": float(latest.get("主力净流入", 0) or 0),
                    "big_inflow": float(latest.get("大单净流入", 0) or 0),
                    "super_inflow": float(latest.get("超大单净流入", 0) or 0),
                    "small_inflow": float(latest.get("小单净流入", 0) or 0),
                    "medium_inflow": float(latest.get("中单净流入", 0) or 0),
                    "source": "efinance",
                    "type": "history_bill",
                }

            return {"source": "efinance", "available": False, "note": f"no bill data for {bk_code}"}

        except Exception as e:
            logger.warning(f"[SectorCollector] efinance capital flow for {efinance_name} failed: {e}")
            return {"source": "efinance", "error": str(e)}

    async def _search_sector_news(self, sector_name: str, d: date) -> List[Dict[str, Any]]:
        """Search recent news for a sector using existing search_service."""
        try:
            from src.search_service import SearchService

            search_service = SearchService()
            results = search_service.search_stock_news(
                stock_code="000001",  # dummy, sector name in focus_keywords
                stock_name=sector_name,
                max_results=10,
                focus_keywords=[sector_name, "行业", "政策"],
            )
            if results and results.results:
                news_items = []
                for item in results.results[:10]:
                    news_items.append({
                        "title": item.title or "",
                        "snippet": item.snippet or "",
                        "url": item.url or "",
                        "source": item.source or "unknown",
                        "published_date": item.published_date.isoformat() if item.published_date else "",
                    })
                return news_items
            return []

        except Exception as e:
            logger.warning(f"[SectorCollector] news search for {sector_name} failed: {e}")
            return []

    def get_targets(self, d: date) -> List[str]:
        return self.sectors

    async def collect_all(self, d: date) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Collect data for all sectors.
        """
        import asyncio

        results = {}
        tasks = []
        for sector in self.sectors:
            tasks.append(self.fetch_with_retry(sector, d, f"sectors/{sector}"))

        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for sector, data in zip(self.sectors, fetched):
            if isinstance(data, Exception):
                logger.error(f"[SectorCollector] {sector}: {data}")
                results[sector] = None
            else:
                results[sector] = data

        return results

    async def get_sector_rankings(self, d: date) -> Dict[str, Any]:
        """
        Get top/bottom sector rankings from efinance get_realtime_quotes.
        """
        self._ensure_efinance()

        try:
            import efinance as ef
            import pandas as pd

            df = ef.stock.get_realtime_quotes(['行业板块'])
            if df is not None and not df.empty:
                change_col = '涨跌幅' if '涨跌幅' in df.columns else 'pct_chg'
                name_col = '股票名称' if '股票名称' in df.columns else 'name'
                if change_col in df.columns and name_col in df.columns:
                    df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
                    df = df.dropna(subset=[change_col])
                    df_sorted = df.sort_values(change_col, ascending=False)

                    top = []
                    for _, row in df_sorted.head(20).iterrows():
                        top.append({
                            "name": row[name_col],
                            "change_pct": float(row[change_col]),
                            "source": "efinance",
                        })

                    bottom = []
                    for _, row in df_sorted.tail(20).iterrows():
                        bottom.append({
                            "name": row[name_col],
                            "change_pct": float(row[change_col]),
                            "source": "efinance",
                        })

                    return {"top": top, "bottom": bottom, "source": "efinance"}

            return {"top": [], "bottom": [], "source": "efinance", "note": "no data"}

        except Exception as e:
            logger.warning(f"[SectorCollector] sector rankings failed: {e}")
            return {"top": [], "bottom": [], "source": "efinance", "error": str(e)}
