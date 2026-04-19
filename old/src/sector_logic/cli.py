# -*- coding: utf-8 -*-
"""
Sector Logic Engine CLI — standalone entry points for collect/analyze/replay/compare.

Usage:
    python -m src.sector_logic.cli --collect --date 2026-04-16
    python -m src.sector_logic.cli --analyze --date 2026-04-16
    python -m src.sector_logic.cli --collect-and-analyze --date 2026-04-16
    python -m src.sector_logic.cli --replay --date 2026-04-10
    python -m src.sector_logic.cli --compare --dates 2026-04-10,2026-04-14
    python -m src.sector_logic.cli --collect --sectors "光伏,AI/算力,半导体,CPO/光通信模块"
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sector_logic.cli")


# Pilot sector list — the 4 sectors to validate first
PILOT_SECTORS = ["光伏", "AI/算力", "半导体", "CPO/光通信模块"]


def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD date string."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {value}. Use YYYY-MM-DD.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sector Logic Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run data collection only (writes to DataStore)",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run analysis only (reads from DataStore, no collection)",
    )

    parser.add_argument(
        "--collect-and-analyze",
        action="store_true",
        help="Run full pipeline: collect + analyze (daily run)",
    )

    parser.add_argument(
        "--replay",
        action="store_true",
        help="Replay analysis on a historical date (read-only, no collection)",
    )

    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare analysis results across multiple dates",
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Analysis date (YYYY-MM-DD). Defaults to today.",
    )

    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        help="Comma-separated dates for compare mode (YYYY-MM-DD,YYYY-MM-DD)",
    )

    parser.add_argument(
        "--sectors",
        type=str,
        default=None,
        help=f"Comma-separated sector names. Default: {','.join(PILOT_SECTORS)}",
    )

    parser.add_argument(
        "--stocks",
        type=str,
        default=None,
        help="Comma-separated stock codes for targeted collection",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for results (JSON). Prints to stdout if not specified.",
    )

    parser.add_argument(
        "--data-root",
        type=str,
        default="./data/sector_logic",
        help="DataStore root directory",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    # Debug commands (Phase 7)
    parser.add_argument(
        "--sector-lifecycle",
        type=str,
        default=None,
        help="Show lifecycle state history for a sector",
    )
    parser.add_argument(
        "--sector-flips",
        type=str,
        default=None,
        help="Show flip event history for a sector",
    )
    parser.add_argument(
        "--sector-issues",
        type=str,
        default=None,
        help="Show issue queue for a sector",
    )

    return parser.parse_args()


async def run_collect(
    d: date,
    sectors: Optional[List[str]] = None,
    stocks: Optional[List[str]] = None,
    data_root: str = "./data/sector_logic",
) -> dict:
    """Run data collection pipeline."""
    from src.sector_logic.datastore import DataStore
    from src.sector_logic.collectors.runner import CollectionRunner

    datastore = DataStore(data_root=data_root)
    runner = CollectionRunner(
        datastore=datastore,
        max_concurrency=10,
        sectors=sectors,
        stock_codes=stocks,
    )

    result = await runner.run(d)
    return result


async def run_analyze(
    d: date,
    data_root: str = "./data/sector_logic",
) -> dict:
    """Run analysis pipeline (read-only from DataStore)."""
    from src.sector_logic.datastore import DataStore
    from src.sector_logic.engine import AnalysisEngine

    datastore = DataStore(data_root=data_root)
    engine = AnalysisEngine(datastore=datastore)

    result = await engine.run(d)
    return result


async def run_replay(
    d: date,
    data_root: str = "./data/sector_logic",
) -> dict:
    """Replay analysis on historical date."""
    from src.sector_logic.datastore import DataStore
    from src.sector_logic.engine import AnalysisEngine

    datastore = DataStore(data_root=data_root)
    engine = AnalysisEngine(datastore=datastore)

    result = await engine.replay(d)
    return result


async def run_compare(
    dates: List[date],
    data_root: str = "./data/sector_logic",
) -> dict:
    """Compare analysis across dates."""
    from src.sector_logic.datastore import DataStore
    from src.sector_logic.engine import AnalysisEngine

    datastore = DataStore(data_root=data_root)
    engine = AnalysisEngine(datastore=datastore)

    result = await engine.compare(dates)
    return result


def main():
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine mode
    if args.collect:
        mode = "collect"
    elif args.analyze:
        mode = "analyze"
    elif args.collect_and_analyze:
        mode = "collect_and_analyze"
    elif args.replay:
        mode = "replay"
    elif args.compare:
        mode = "compare"
    else:
        # Default: collect-and-analyze for today
        mode = "collect_and_analyze"
        logger.info("No mode specified, defaulting to --collect-and-analyze")

    # Parse date(s)
    if mode == "compare" and args.dates:
        dates = [parse_date(d) for d in args.dates.split(",")]
    else:
        d = parse_date(args.date) if args.date else date.today()

    # Parse sectors
    sectors = PILOT_SECTORS
    if args.sectors:
        sectors = [s.strip() for s in args.sectors.split(",") if s.strip()]

    # Parse stocks
    stocks = None
    if args.stocks:
        stocks = [s.strip() for s in args.stocks.split(",") if s.strip()]

    logger.info(f"Mode: {mode}")
    logger.info(f"Date(s): {d.isoformat() if mode != 'compare' else [x.isoformat() for x in dates]}")
    logger.info(f"Sectors: {sectors}")
    if stocks:
        logger.info(f"Stocks: {stocks}")

    # Run
    try:
        if mode == "collect":
            result = asyncio.run(run_collect(d, sectors=sectors, stocks=stocks, data_root=args.data_root))
        elif mode == "analyze":
            result = asyncio.run(run_analyze(d, data_root=args.data_root))
        elif mode == "collect_and_analyze":
            collect_result = asyncio.run(run_collect(d, sectors=sectors, stocks=stocks, data_root=args.data_root))
            logger.info("Collection complete, running analysis...")
            result = asyncio.run(run_analyze(d, data_root=args.data_root))
        elif mode == "replay":
            result = asyncio.run(run_replay(d, data_root=args.data_root))
        elif mode == "compare":
            result = asyncio.run(run_compare(dates, data_root=args.data_root))
        else:
            logger.error(f"Unknown mode: {mode}")
            sys.exit(1)

        # Output
        output_str = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str)
            logger.info(f"Results written to {args.output}")
        else:
            print(output_str)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
