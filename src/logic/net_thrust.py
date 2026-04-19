"""Net thrust calculation - aggregates positive/negative events with anti-logic flagging."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Tuple
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import EventModel, LogicModel, LogicScore, LLMServiceStatus

logger = logging.getLogger(__name__)


@dataclass
class NetThrustResult:
    """Net thrust calculation result."""
    logic_id: str
    positive_strength: Decimal  # Sum of positive events
    negative_strength: Decimal  # Sum of negative events
    net_thrust: Decimal  # positive - negative
    has_anti_logic: bool  # Both positive and negative events exist
    event_count: int
    positive_event_count: int
    negative_event_count: int
    snapshot_date: date


class NetThrustCalculator:
    """Calculate net thrust with anti-logic flagging."""

    def calculate(self, events: List[EventModel]) -> NetThrustResult:
        """Calculate net thrust from list of events.

        Args:
            events: List of valid, non-expired events for a single logic_id

        Returns:
            NetThrustResult with all metrics
        """
        if not events:
            return NetThrustResult(
                logic_id="",
                positive_strength=Decimal("0"),
                negative_strength=Decimal("0"),
                net_thrust=Decimal("0"),
                has_anti_logic=False,
                event_count=0,
                positive_event_count=0,
                negative_event_count=0,
                snapshot_date=date.today()
            )

        # Separate positive and negative events
        positive_events = [e for e in events if e.direction.name == "positive"]
        negative_events = [e for e in events if e.direction.name == "negative"]

        # Sum strengths (already adjusted for importance and decay)
        positive_strength = sum(
            (Decimal(ev.strength_adjusted) if ev.strength_adjusted else Decimal(ev.strength_raw))
            for ev in positive_events
        )
        negative_strength = sum(
            (Decimal(ev.strength_adjusted) if ev.strength_adjusted else Decimal(ev.strength_raw))
            for ev in negative_events
        )

        # Net thrust
        net_thrust = positive_strength - negative_strength

        # Anti-logic flag: both sides have non-zero strength
        has_anti_logic = (positive_strength > 0 and negative_strength > 0)

        return NetThrustResult(
            logic_id=events[0].logic_id,
            positive_strength=positive_strength,
            negative_strength=negative_strength,
            net_thrust=net_thrust,
            has_anti_logic=has_anti_logic,
            event_count=len(events),
            positive_event_count=len(positive_events),
            negative_event_count=len(negative_events),
            snapshot_date=date.today()
        )


class LogicSnapshotService:
    """Generate daily logic score snapshots."""

    def __init__(self):
        self.calculator = NetThrustCalculator()

    async def generate_daily_snapshot(self, snapshot_date: date) -> List[NetThrustResult]:
        """Generate daily snapshot for all active logics.

        Steps:
        1. Fetch all active logics
        2. For each logic, get valid events
        3. Calculate net thrust
        4. Persist to logic_scores table

        Returns:
            List of NetThrustResult for all logics
        """
        async with async_session_maker() as session:
            # Fetch active logics
            result = await session.execute(
                select(LogicModel).where(LogicModel.is_active == True)
            )
            logics = result.scalars().all()

        logger.info(f"Generating snapshot for {len(logics)} active logics")

        results = []

        for logic in logics:
            # Get valid events for this logic
            events = await self._get_valid_events(logic.logic_id, snapshot_date)

            # Calculate net thrust
            thrust_result = self.calculator.calculate(events)
            results.append(thrust_result)

        # Persist all results
        await self._persist_snapshots(results)

        return results

    async def _get_valid_events(
        self,
        logic_id: str,
        snapshot_date: date
    ) -> List[EventModel]:
        """Get non-expired events for logic as of snapshot_date."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(EventModel).where(
                    EventModel.logic_id == logic_id,
                    EventModel.event_date <= snapshot_date,
                    EventModel.is_expired == False
                ).order_by(EventModel.event_date.desc())
            )
            return result.scalars().all()

    async def _persist_snapshots(
        self,
        results: List[NetThrustResult]
    ) -> None:
        """Persist net thrust results to logic_scores table."""
        async with async_session_maker() as session:
            for result in results:
                # Check if record exists
                existing = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == result.logic_id,
                        LogicScore.snapshot_date == result.snapshot_date
                    )
                )
                existing = existing.scalar_one_or_none()

                if existing:
                    # Update fields
                    existing.raw_score = result.positive_strength + result.negative_strength
                    existing.decayed_score = abs(result.net_thrust)
                    existing.net_thrust = result.net_thrust
                    existing.has_anti_logic = result.has_anti_logic
                    existing.event_count = result.event_count
                    existing.positive_event_count = result.positive_event_count
                    existing.negative_event_count = result.negative_event_count
                else:
                    # Insert new
                    logic_score = LogicScore(
                        logic_id=result.logic_id,
                        snapshot_date=result.snapshot_date,
                        raw_score=result.positive_strength + result.negative_strength,
                        decayed_score=abs(result.net_thrust),
                        net_thrust=result.net_thrust,
                        has_anti_logic=result.has_anti_logic,
                        event_count=result.event_count,
                        positive_event_count=result.positive_event_count,
                        negative_event_count=result.negative_event_count,
                        llm_service_status=LLMServiceStatus.full,
                    )
                    session.add(logic_score)

            await session.commit()

        logger.info(f"Persisted {len(results)} logic score snapshots")


class LogicScoreQueries:
    """Query interface for downstream layers."""

    @staticmethod
    async def get_latest_scores() -> Dict[str, Decimal]:
        """Get latest net thrust scores for all logics."""
        async with async_session_maker() as session:
            # Get max snapshot_date
            max_date_result = await session.execute(
                select(func.max(LogicScore.snapshot_date))
            )
            max_date = max_date_result.scalar()

            if not max_date:
                return {}

            # Get scores for max_date
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.snapshot_date == max_date
                )
            )
            scores = result.scalars().all()

            return {s.logic_id: s.net_thrust for s in scores if s.net_thrust}

    @staticmethod
    async def get_anti_logic_flags(
        snapshot_date: date = None
    ) -> List[str]:
        """Get list of logic_ids with anti-logic flags."""
        snapshot_date = snapshot_date or date.today()

        async with async_session_maker() as session:
            result = await session.execute(
                select(LogicScore.logic_id).where(
                    LogicScore.snapshot_date == snapshot_date,
                    LogicScore.has_anti_logic == True
                )
            )
            return [row.logic_id for row in result]
