#!/usr/bin/env python3
"""Standalone daily job script for system cron.

This script is invoked by system cron at scheduled times.
Per D-03: APScheduler provides CronTrigger logic, but system cron triggers execution.

Usage (crontab):
    30 15 * * 1-5 cd /path/to/stock_logic && python scripts/daily_job.py >> logs/cron.log 2>&1
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "daily_job.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


async def main() -> int:
    """Run daily market data job.

    Returns:
        Exit code: 0 for success, 1 for error.
    """
    logger.info("=" * 50)
    logger.info("Daily job script started")
    logger.info(f"Python: {sys.version}")
    logger.info("=" * 50)

    try:
        from src.scheduler.daily_job import daily_market_data_job
        from src.macro.scheduler import create_macro_scheduler

        # Initialize macro scheduler (runs monthly on 15th at 16:00 CST)
        scheduler = create_macro_scheduler()
        scheduler.start()
        logger.info("Macro scheduler initialized (monthly refresh on 15th at 16:00 CST)")

        # Run daily job
        await daily_market_data_job()

        logger.info("Daily job completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Daily job failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
