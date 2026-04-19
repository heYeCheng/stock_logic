"""Macro scheduler - monthly refresh and event-triggered updates."""

import logging
from datetime import date
from typing import Dict, Any, Optional

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


async def refresh_macro_data() -> None:
    """Monthly macro data refresh job."""
    logger.info("Starting monthly macro data refresh")

    try:
        from src.macro.service import MacroService

        service = MacroService()
        snapshot = await service.compute_snapshot(date.today())

        logger.info(f"Macro snapshot computed: {snapshot.snapshot_date}")
        logger.info(f"  Composite score: {snapshot.composite_score}")
        logger.info(f"  Quadrant: {snapshot.quadrant}")
        logger.info(f"  Macro multiplier: {snapshot.macro_multiplier}")

    except Exception as e:
        logger.error(f"Macro refresh failed: {e}", exc_info=True)
        raise


def create_macro_scheduler(scheduler=None):
    """
    Create APScheduler with monthly cron trigger for macro refresh.

    Args:
        scheduler: Optional existing scheduler instance

    Returns:
        Scheduler with macro job added
    """
    if scheduler is None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()

    # 15th of each month, 16:00 CST (Asia/Shanghai)
    trigger = CronTrigger(
        minute=0,
        hour=16,
        day=15,
        month='*',
        timezone='Asia/Shanghai'
    )

    scheduler.add_job(
        refresh_macro_data,
        trigger=trigger,
        id='macro_monthly_refresh',
        name='Monthly Macro Data Refresh',
        replace_existing=True
    )

    logger.info("Macro scheduler created: monthly refresh on 15th at 16:00 CST")
    return scheduler


async def trigger_manual_refresh() -> Dict[str, Any]:
    """
    Manually trigger macro data refresh.

    Returns:
        dict with status and snapshot summary
    """
    from src.macro.service import MacroService

    service = MacroService()
    snapshot = await service.compute_snapshot(date.today())

    return {
        "status": "success",
        "snapshot_date": str(snapshot.snapshot_date),
        "composite_score": float(snapshot.composite_score) if snapshot.composite_score else None,
        "quadrant": snapshot.quadrant.value if snapshot.quadrant else None,
        "macro_multiplier": float(snapshot.macro_multiplier) if snapshot.macro_multiplier else None
    }


async def trigger_event_refresh(event_type: str, event_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Event-triggered macro refresh.

    Supported events (Phase 3+):
    - policy_announcement: PBOC policy change
    - data_revision: NBS revises historical data
    - global_shock: Fed rate decision, geopolitical event

    Phase 2: Stub - logs event, no action

    Args:
        event_type: Type of event
        event_data: Event payload

    Returns:
        dict with status
    """
    logger.info(f"Event-triggered refresh received: {event_type}")
    if event_data:
        logger.debug(f"Event data: {event_data}")

    # Phase 2: No-op, just log
    # Phase 3: Implement event detection and refresh logic

    return {
        "status": "logged",
        "message": f"Event {event_type} logged for Phase 3 processing"
    }
