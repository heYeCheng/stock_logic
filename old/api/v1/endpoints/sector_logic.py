# -*- coding: utf-8 -*-
"""
===================================
Sector Logic Engine API Endpoints
===================================

职责：
1. GET /api/v1/logic/macro — 最新宏观数据
2. GET /api/v1/logic/macro/{date} — 指定日期宏观数据
3. GET /api/v1/logic/sectors — 板块列表
4. GET /api/v1/logic/sectors/{sector}/result — 板块分析结果
5. GET /api/v1/logic/sectors/{sector}/flips — 翻转事件历史
6. GET /api/v1/logic/sectors/{sector}/issues — 排查清单
7. GET /api/v1/logic/sectors/{sector}/lifecycle — 生命周期状态
8. GET /api/v1/logic/sectors/{sector}/radar/{date} — 指定日期雷达图
9. GET /api/v1/selection/top — 综合选股结果（分层）
10. GET /api/v1/selection/stock/{code} — 个股雷达详情
11. POST /api/v1/logic/collect — 触发数据采集
12. POST /api/v1/logic/analyze — 手动触发分析
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_config_dep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SectorLogic"])

# === Helpers ===

def _get_datastore():
    """Get DataStore instance (lazy import)."""
    from src.sector_logic.datastore import DataStore
    return DataStore()


def _get_sector_data(d: date, sector: str, datastore=None):
    """Load sector snapshot data."""
    ds = datastore or _get_datastore()
    return ds.get_snapshot(d, f"sectors/{sector}")


# === Macro Endpoints ===

@router.get("/logic/macro")
def get_macro_result(date_str: Optional[str] = Query(None, description="YYYY-MM-DD")):
    """获取宏观分析结果，默认今天。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    ds = _get_datastore()

    # Try explicit macro_result key first, then macro
    result = ds.get_snapshot(d, "macro_result") or ds.get_snapshot(d, "macro")
    if result is None:
        raise HTTPException(status_code=404, detail=f"No macro data for {d.isoformat()}")

    # Normalize to expected frontend shape
    return {
        "macro_thesis_score": result.get("macro_thesis_score", 0.5),
        "macro_state": result.get("macro_state", "neutral"),
        "summary": result.get("summary", ""),
        "dimension_scores": result.get("dimension_scores", {}),
    }


@router.get("/logic/macro/{date_str}")
def get_macro_result_by_date(date_str: str):
    """获取指定日期的宏观数据。"""
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return get_macro_result(date_str)


# === Sector Endpoints ===

@router.get("/logic/sectors")
def get_sectors():
    """获取有数据的板块列表。"""
    ds = _get_datastore()
    dates = ds.list_available_dates()
    if not dates:
        return []

    latest = max(dates)
    sectors_dir = ds.snapshots_dir / latest.isoformat() / "sectors"
    if not sectors_dir.exists():
        return []

    return [f.stem for f in sectors_dir.glob("*.json")]


@router.get("/logic/sectors/{sector}/result")
def get_sector_result(sector: str, date_str: Optional[str] = Query(None)):
    """获取板块分析结果。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    ds = _get_datastore()

    snapshot = ds.get_snapshot(d, f"sector_results/{sector}")
    if snapshot is None:
        # Fallback: try sectors/<sector> (raw data)
        snapshot = _get_sector_data(d, sector, ds)

    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No sector data for {sector} on {d.isoformat()}")

    # Ensure required frontend fields
    if "sector_logic_strength" not in snapshot:
        snapshot["sector_logic_strength"] = snapshot.get("sector_thesis_score", 0.5)
    if "sector_lifecycle_stage" not in snapshot:
        snapshot["sector_lifecycle_stage"] = "discovery"
    if "sector_lifecycle_status" not in snapshot:
        snapshot["sector_lifecycle_status"] = "emerging"
    if "sector_strength_trend" not in snapshot:
        snapshot["sector_strength_trend"] = "stable"
    if "sector_logic_strength_framework" not in snapshot:
        snapshot["sector_logic_strength_framework"] = []
    if "radar_logic" not in snapshot:
        snapshot["radar_logic"] = snapshot.get("radar_logic", 5.0)
    if "radar_fundamental" not in snapshot:
        snapshot["radar_fundamental"] = snapshot.get("radar_fundamental", 5.0)
    if "radar_technical" not in snapshot:
        snapshot["radar_technical"] = snapshot.get("radar_technical", 5.0)
    if "radar_capital_flow" not in snapshot:
        snapshot["radar_capital_flow"] = snapshot.get("radar_capital_flow", 5.0)
    if "radar_sentiment" not in snapshot:
        snapshot["radar_sentiment"] = snapshot.get("radar_sentiment", 5.0)
    if "sector_price_score" not in snapshot:
        snapshot["sector_price_score"] = 0.5
    if "sector_macro_adjustment" not in snapshot:
        snapshot["sector_macro_adjustment"] = 0.0
    if "snapshot_date" not in snapshot:
        snapshot["snapshot_date"] = d.isoformat()

    return snapshot


@router.get("/logic/sectors/{sector}/flips")
def get_sector_flips(sector: str):
    """获取板块翻转事件历史。"""
    ds = _get_datastore()
    dates = ds.list_available_dates()
    if not dates:
        return []

    # Collect flip events from all dates for this sector
    events = []
    for d in sorted(dates, reverse=True):
        snapshot = ds.get_snapshot(d, f"sector_results/{sector}")
        if snapshot and snapshot.get("flip_events"):
            events.extend(snapshot["flip_events"])

    return events


@router.get("/logic/sectors/{sector}/issues")
def get_sector_issues(sector: str, date_str: Optional[str] = Query(None)):
    """获取板块排查清单。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    ds = _get_datastore()

    snapshot = ds.get_snapshot(d, f"sector_results/{sector}")
    if snapshot is None:
        return []

    return snapshot.get("issue_queue", [])


@router.get("/logic/sectors/{sector}/lifecycle")
def get_sector_lifecycle(sector: str):
    """获取板块生命周期状态。"""
    ds = _get_datastore()
    # Lifecycle states are stored separately
    lifecycle_dir = ds.snapshots_dir / "lifecycle"
    if not lifecycle_dir.exists():
        return []

    states = []
    for f in lifecycle_dir.glob(f"*{sector}*"):
        if f.suffix == ".json":
            with open(f, "r", encoding="utf-8") as fh:
                states.append(json.load(fh))
    return states


@router.get("/logic/sectors/{sector}/radar/{date_str}")
def get_sector_radar(sector: str, date_str: str):
    """获取板块雷达图数据。"""
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format.")

    snapshot = _get_sector_data(d, sector)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No data for {sector} on {d.isoformat()}")

    return {
        "逻辑面": snapshot.get("radar_logic", 5.0),
        "基本面": snapshot.get("radar_fundamental", 5.0),
        "技术面": snapshot.get("radar_technical", 5.0),
        "资金面": snapshot.get("radar_capital_flow", 5.0),
        "情绪面": snapshot.get("radar_sentiment", 5.0),
    }


# === Stock Selection Endpoints ===

@router.get("/selection/top")
def get_selection_top(date_str: Optional[str] = Query(None)):
    """获取综合选股结果（分层）。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    ds = _get_datastore()

    result = ds.get_snapshot(d, "analysis_result")
    if result is None:
        raise HTTPException(status_code=404, detail=f"No analysis result for {d.isoformat()}")

    composite = result.get("composite", {})
    if not composite:
        raise HTTPException(status_code=404, detail="No composite selection data.")

    return {
        "recommendations": composite.get("recommendations", []),
        "tiers": composite.get("tiers", {}),
        "macro_switch_status": composite.get("macro_switch_status", {"triggered": False}),
        "total_count": composite.get("total_count", 0),
    }


@router.get("/selection/stock/{code}")
def get_stock_detail(code: str, date_str: Optional[str] = Query(None)):
    """获取个股雷达详情。"""
    d = date.fromisoformat(date_str) if date_str else date.today()
    ds = _get_datastore()

    result = ds.get_snapshot(d, f"stock_results/{code}")
    if result is None:
        # Fallback: try stock snapshot data
        result = ds.get_snapshot(d, f"stocks/{code}")

    if result is None:
        raise HTTPException(status_code=404, detail=f"No stock data for {code} on {d.isoformat()}")

    return result


# === Analysis Trigger ===

@router.post("/logic/analyze")
async def trigger_analysis(date_str: Optional[str] = Query(None)):
    """手动触发 Sector Logic 分析。"""
    import asyncio
    from datetime import date as date_type
    from src.sector_logic.engine import AnalysisEngine
    from src.sector_logic.skill_loader import SectorLogicSkillLoader

    d = date_type.fromisoformat(date_str) if date_str else date_type.today()

    # Check if sector data exists first, before spawning analysis
    ds = _get_datastore()
    sectors_dir = ds.snapshots_dir / d.isoformat() / "sectors"
    sector_count = len(list(sectors_dir.glob("*.json"))) if sectors_dir.exists() else 0
    if sector_count == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No sector data found for {d.isoformat()}. "
                   f"Run data collection first: python -m src.sector_logic.cli --collect --date {d.isoformat()}"
        )

    # Run analysis in a thread pool (AnalysisEngine.run is async)
    async def _run():
        engine = AnalysisEngine(skill_loader=SectorLogicSkillLoader())
        result = await engine.run(d)

        # Save result
        ds.write_snapshot(d, "analysis_result", result)
        for sector, sector_result in result.get("sector_results", {}).items():
            ds.write_snapshot(d, f"sector_results/{sector}", sector_result.get("sector_logic", {}))

        return result

    result = await _run()

    sectors_analyzed = len(result.get("sector_results", {}))
    return {"status": "ok", "date": d.isoformat(), "sectors_analyzed": sectors_analyzed}
