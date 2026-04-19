"""Event scorecard rule engine - applies加减分 rules, decay, and validity tracking."""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import EventModel, LogicScore, LLMServiceStatus

logger = logging.getLogger(__name__)


@dataclass
class ScorecardConfig:
    """Scorecard configuration."""
    daily_decay_rate: Decimal = Decimal("0.95")
    importance_multipliers: Dict[str, Decimal] = field(default_factory=lambda: {
        "high": Decimal("1.5"),
        "medium": Decimal("1.0"),
        "low": Decimal("0.5"),
    })
    validity_default_days: int = 30
    strength_min: Decimal = Decimal("0.1")
    strength_max: Decimal = Decimal("1.0")
    confidence_min: float = 0.6

    @classmethod
    def from_yaml(cls, path: str) -> "ScorecardConfig":
        """Load config from YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            scoring = data.get("scoring", {})
            decay = scoring.get("decay", {})
            thresholds = scoring.get("thresholds", {})

            return cls(
                daily_decay_rate=Decimal(str(decay.get("daily_rate", 0.95))),
                importance_multipliers={
                    k: Decimal(str(v))
                    for k, v in scoring.get("importance_multipliers", {}).items()
                },
                validity_default_days=scoring.get("validity", {}).get("default_days", 30),
                strength_min=Decimal(str(thresholds.get("strength_min", 0.1))),
                strength_max=Decimal(str(thresholds.get("strength_max", 1.0))),
                confidence_min=thresholds.get("confidence_min", 0.6),
            )
        except Exception as e:
            logger.warning(f"Failed to load config from {path}, using defaults: {e}")
            return cls()


@dataclass
class ScorecardEvent:
    """Event in scorecard with computed fields."""
    event_id: str
    logic_id: str
    event_date: date
    strength_raw: Decimal
    direction: str
    importance_level: str
    validity_days: int
    created_at: date = field(default_factory=date.today)

    # Computed fields
    strength_adjusted: Decimal = field(default=Decimal("0"))
    decay_factor: Decimal = field(default=Decimal("1"))
    is_valid: bool = field(default=True)
    days_elapsed: int = field(default=0)


class EventScorecard:
    """Scorecard for a single logic_id.

    Applies加减分 rules, natural decay, and tracks validity periods.
    """

    def __init__(
        self,
        logic_id: str,
        config: ScorecardConfig,
    ):
        self.logic_id = logic_id
        self.config = config
        self.events: List[ScorecardEvent] = []
        self.current_score: Decimal = Decimal("0")
        self.last_updated: date = date.today()

    def add_event(self, event: ScorecardEvent) -> None:
        """Add event to scorecard with validation and scoring."""

        # Apply importance multiplier
        multiplier = self.config.importance_multipliers.get(
            event.importance_level, Decimal("1.0")
        )
        event.strength_adjusted = event.strength_raw * multiplier

        # Cap at max
        if event.strength_adjusted > self.config.strength_max:
            event.strength_adjusted = self.config.strength_max

        # Ignore events below minimum strength
        if event.strength_adjusted < self.config.strength_min:
            logger.debug(f"Event {event.event_id} strength too low, ignoring")
            return

        self.events.append(event)
        self._recalculate_score()

    def apply_decay(self, target_date: date = None) -> None:
        """Apply natural decay to all events."""
        target_date = target_date or date.today()
        days_elapsed = (target_date - self.last_updated).days

        if days_elapsed <= 0:
            return

        logger.debug(f"Applying {days_elapsed} days decay to scorecard {self.logic_id}")

        # Apply decay factor: score *= decay_rate ^ days
        decay_multiplier = self.config.daily_decay_rate ** days_elapsed

        for event in self.events:
            event.days_elapsed += days_elapsed
            event.decay_factor = decay_multiplier

            # Check validity
            if event.days_elapsed > event.validity_days:
                event.is_valid = False

        self._recalculate_score()
        self.last_updated = target_date

    def _recalculate_score(self) -> None:
        """Recalculate current score from valid events."""
        valid_events = [e for e in self.events if e.is_valid]

        self.current_score = sum(
            (e.strength_adjusted * e.decay_factor for e in valid_events),
            Decimal("0")
        )

    def get_summary(self) -> "ScorecardSummary":
        """Get scorecard summary."""
        valid_events = [e for e in self.events if e.is_valid]
        expired_events = [e for e in self.events if not e.is_valid]

        return ScorecardSummary(
            logic_id=self.logic_id,
            current_score=self.current_score,
            event_count=len(valid_events),
            expired_count=len(expired_events),
            last_updated=self.last_updated
        )


@dataclass
class ScorecardSummary:
    """Scorecard summary for persistence."""
    logic_id: str
    current_score: Decimal
    event_count: int
    expired_count: int
    last_updated: date


class ScorecardManager:
    """Manage scorecards for all logics."""

    def __init__(self, config_path: str = None):
        if config_path:
            self.config = ScorecardConfig.from_yaml(config_path)
        else:
            self.config = ScorecardConfig()
        self.scorecards: Dict[str, EventScorecard] = {}

    def get_or_create_scorecard(self, logic_id: str) -> EventScorecard:
        """Get existing scorecard or create new one."""
        if logic_id not in self.scorecards:
            self.scorecards[logic_id] = EventScorecard(logic_id, self.config)
        return self.scorecards[logic_id]

    def process_daily_snapshot(self, snapshot_date: date) -> Dict[str, Decimal]:
        """Process daily snapshot: apply decay and return scores."""
        scores = {}

        for logic_id, scorecard in self.scorecards.items():
            scorecard.apply_decay(snapshot_date)
            summary = scorecard.get_summary()
            scores[logic_id] = summary.current_score

        return scores

    async def persist_scores(
        self,
        scores: Dict[str, Decimal],
        snapshot_date: date
    ) -> None:
        """Persist scores to logic_scores table."""
        async with async_session_maker() as session:
            for logic_id, score in scores.items():
                # Check if record exists
                result = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == logic_id,
                        LogicScore.snapshot_date == snapshot_date
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update
                    existing.raw_score = score
                    existing.decayed_score = score
                else:
                    # Insert
                    logic_score = LogicScore(
                        logic_id=logic_id,
                        snapshot_date=snapshot_date,
                        raw_score=score,
                        decayed_score=score,
                        event_count=len(self.scorecards[logic_id].events),
                        llm_service_status=LLMServiceStatus.full,
                    )
                    session.add(logic_score)

            await session.commit()

        logger.info(f"Persisted {len(scores)} logic scores for {snapshot_date}")
