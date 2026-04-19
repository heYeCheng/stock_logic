"""Daily market data job using APScheduler."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.data.manager import DataFetcherManager
from src.database.connection import async_session_maker
from src.database.models import MarketDataModel
from sqlalchemy import select


logger = logging.getLogger("daily_job")


async def daily_market_data_job() -> None:
    """Fetch and store daily market data.

    This job:
    1. Fetches stock list from data sources
    2. For each stock (limited to 10 for Phase 1 testing), fetches daily data
    3. Stores data in market_data table
    4. Logs execution status
    """
    logger.info(f"Daily job started at {datetime.now()}")

    manager = DataFetcherManager()
    records_inserted = 0

    try:
        # Fetch stock list
        logger.info("Fetching stock list...")
        stock_list = manager.get_stock_list()

        if stock_list.empty:
            logger.warning("Stock list is empty, nothing to fetch")
            return

        # Limit to 10 stocks for Phase 1 testing
        stocks_to_fetch = stock_list.head(10)
        logger.info(f"Fetching data for {len(stocks_to_fetch)} stocks")

        async with async_session_maker() as session:
            for _, row in stocks_to_fetch.iterrows():
                ts_code = row.get("ts_code")
                if not ts_code:
                    continue

                logger.info(f"Fetching daily data for {ts_code}")
                df, source = manager.get_daily_data(ts_code, days=1)

                if df.empty:
                    logger.warning(f"No data for {ts_code} from {source}")
                    continue

                # Create MarketDataModel instance
                for _, record in df.iterrows():
                    market_data = MarketDataModel(
                        ts_code=ts_code,
                        trade_date=record.get("trade_date"),
                        open=record.get("open", 0),
                        high=record.get("high", 0),
                        low=record.get("low", 0),
                        close=record.get("close", 0),
                        volume=record.get("volume", 0),
                        amount=record.get("amount", 0),
                        source=source,
                    )
                    session.add(market_data)
                    records_inserted += 1

            # Commit all records
            await session.commit()
            logger.info(f"Daily job completed: {records_inserted} records inserted")

    except Exception as e:
        logger.error(f"Daily job failed: {e}", exc_info=True)
        raise


def create_scheduler() -> AsyncIOScheduler:
    """Create APScheduler with CronTrigger for daily job.

    Schedule: 15:30 CST on weekdays (mon-fri)
    Timezone: Asia/Shanghai (from settings)

    Returns:
        Configured AsyncIOScheduler instance.
    """
    scheduler = AsyncIOScheduler()

    # Add daily job with cron trigger
    scheduler.add_job(
        daily_market_data_job,
        CronTrigger(
            hour=15,
            minute=30,
            day_of_week="mon-fri",
            timezone=settings.scheduler_timezone,
        ),
        id="daily_market_data",
        name="Daily Market Data Fetch",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler created: daily_market_data_job at 15:30 {settings.scheduler_timezone} mon-fri"
    )

    return scheduler


def run_scheduler() -> None:
    """Run scheduler until stopped.

    Blocks and runs the scheduler loop.
    Handles KeyboardInterrupt gracefully.

    Usage:
        from src.scheduler import run_scheduler
        run_scheduler()
    """
    scheduler = create_scheduler()
    scheduler.start()

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        # Keep running until interrupted
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler shutting down...")
        scheduler.shutdown()
