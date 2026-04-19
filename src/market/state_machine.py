"""State machine service for sector three-state determination with hysteresis."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.database.connection import get_db_session
from src.market.models import SectorScore, SectorState


class StateTransitionService:
    """Manage sector state transitions with hysteresis."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_db_session()
        self.state_history: Dict[str, List[Tuple[date, SectorState]]] = {}

    async def update_state(
        self, sector_id: str, snapshot: SectorScore
    ) -> SectorState:
        """Update sector state based on composite score and history.

        Args:
            sector_id: The sector identifier
            snapshot: The SectorScore snapshot with composite_score

        Returns:
            The new SectorState after applying hysteresis logic
        """
        # Get previous state from database
        previous_state = await self._get_previous_state(sector_id)

        # Calculate new state with hysteresis
        new_state = SectorState.from_composite_score(
            snapshot.composite_score, previous_state
        )

        # Load history for consecutive days calculation
        await self._load_history(sector_id)

        # Calculate consecutive days in current state
        consecutive_days = self._calculate_consecutive_days(sector_id, new_state)

        # Calculate confidence (distance from boundaries)
        confidence = self._calculate_confidence(snapshot.composite_score, new_state)

        # Update in-memory history
        if sector_id not in self.state_history:
            self.state_history[sector_id] = []
        self.state_history[sector_id].append((snapshot.snapshot_date, new_state))

        # Persist to database
        await self._persist_transition(
            sector_id, new_state, consecutive_days, confidence
        )

        return new_state

    async def _get_previous_state(
        self, sector_id: str
    ) -> Optional[SectorState]:
        """Get the most recent state for a sector from database."""
        stmt = (
            select(SectorScore)
            .where(SectorScore.sector_id == sector_id)
            .where(SectorScore.state.isnot(None))
            .order_by(SectorScore.snapshot_date.desc())
            .limit(1)
        )
        result = self.session.execute(stmt).scalars().first()
        return result.state if result else None

    async def _load_history(self, sector_id: str) -> None:
        """Load state history from database for consecutive days calculation."""
        if sector_id in self.state_history:
            return  # Already loaded

        # Load last 30 days of history
        stmt = (
            select(SectorScore)
            .where(SectorScore.sector_id == sector_id)
            .where(SectorScore.state.isnot(None))
            .order_by(SectorScore.snapshot_date.desc())
            .limit(30)
        )
        results = self.session.execute(stmt).scalars().all()
        self.state_history[sector_id] = [
            (row.snapshot_date, row.state) for row in results
        ]

    def _calculate_consecutive_days(
        self, sector_id: str, current_state: SectorState
    ) -> int:
        """Calculate how many consecutive days the sector has been in current state."""
        history = self.state_history.get(sector_id, [])
        if not history:
            return 1

        consecutive = 0
        for _, state in history:
            if state == current_state:
                consecutive += 1
            else:
                break

        return max(consecutive, 1)

    def _calculate_confidence(
        self, score: Decimal, state: SectorState
    ) -> float:
        """Calculate how far score is from state boundaries.

        Args:
            score: The composite score
            state: The current state

        Returns:
            Confidence value 0.0-1.0, where higher means further from boundaries
        """
        if state == SectorState.weak:
            # Distance from 0.35 boundary (weak upper bound)
            boundary = Decimal("0.35")
            if score >= boundary:
                return 0.0
            # Normalize: max distance is 0.35 (score=0)
            return float((boundary - score) / boundary)

        elif state == SectorState.overheated:
            # Distance from 0.70 boundary (overheated lower bound)
            boundary = Decimal("0.70")
            if score <= boundary:
                return 0.0
            # Normalize: max distance is 0.30 (score=1.0)
            return float((score - boundary) / Decimal("0.30"))

        else:  # normal
            # Distance from nearest boundary (0.35 or 0.70)
            dist_to_weak = float(score - Decimal("0.35"))
            dist_to_hot = float(Decimal("0.70") - score)

            if dist_to_weak < 0 or dist_to_hot < 0:
                return 0.0

            # Normalize by half the normal range (0.175)
            max_dist = float(Decimal("0.175"))
            return min(dist_to_weak, dist_to_hot) / max_dist

    async def _persist_transition(
        self,
        sector_id: str,
        state: SectorState,
        consecutive_days: int,
        confidence: float,
    ) -> None:
        """Persist the state transition to database."""
        # Find the latest snapshot for this sector and update it
        stmt = (
            select(SectorScore)
            .where(SectorScore.sector_id == sector_id)
            .order_by(SectorScore.snapshot_date.desc())
            .limit(1)
        )
        result = self.session.execute(stmt).scalars().first()

        if result:
            result.state = state
            result.state_confidence = confidence
            result.consecutive_days = consecutive_days
            self.session.commit()


class SectorStateQueries:
    """Query interface for sector states."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_db_session()

    async def get_current_states(self) -> Dict[str, SectorState]:
        """Get current state for all sectors.

        Returns:
            Dict mapping sector_id to current SectorState
        """
        # Get the latest snapshot for each sector
        subquery = (
            select(
                SectorScore.sector_id,
                func.max(SectorScore.snapshot_date).label("max_date"),
            )
            .group_by(SectorScore.sector_id)
            .subquery()
        )

        stmt = select(SectorScore).join(
            subquery,
            and_(
                SectorScore.sector_id == subquery.c.sector_id,
                SectorScore.snapshot_date == subquery.c.max_date,
            ),
        )

        results = self.session.execute(stmt).scalars().all()
        return {
            row.sector_id: row.state
            for row in results
            if row.state is not None
        }

    async def get_sectors_by_state(self, state: SectorState) -> List[str]:
        """Get list of sectors in a given state.

        Args:
            state: The target state

        Returns:
            List of sector_ids currently in that state
        """
        current_states = await self.get_current_states()
        return [
            sector_id
            for sector_id, sector_state in current_states.items()
            if sector_state == state
        ]

    async def get_state_history(
        self, sector_id: str, days: int = 30
    ) -> List[Tuple[date, SectorState]]:
        """Get state history for a sector.

        Args:
            sector_id: The sector identifier
            days: Number of days to look back

        Returns:
            List of (snapshot_date, SectorState) tuples
        """
        from datetime import timedelta

        cutoff_date = date.today() - timedelta(days=days)

        stmt = (
            select(SectorScore)
            .where(SectorScore.sector_id == sector_id)
            .where(SectorScore.snapshot_date >= cutoff_date)
            .where(SectorScore.state.isnot(None))
            .order_by(SectorScore.snapshot_date.desc())
        )

        results = self.session.execute(stmt).scalars().all()
        return [(row.snapshot_date, row.state) for row in results]

    async def get_recent_transitions(
        self, days: int = 7
    ) -> List[Dict]:
        """Get sectors that changed state recently.

        Args:
            days: Number of days to look back

        Returns:
            List of dicts with sector_id, from_state, to_state, transition_date
        """
        from datetime import timedelta

        cutoff_date = date.today() - timedelta(days=days)

        stmt = (
            select(SectorScore)
            .where(SectorScore.snapshot_date >= cutoff_date)
            .where(SectorScore.state.isnot(None))
            .order_by(SectorScore.sector_id, SectorScore.snapshot_date.desc())
        )

        results = self.session.execute(stmt).scalars().all()

        # Group by sector and find transitions
        sector_data: Dict[str, List[Tuple[date, SectorState]]] = {}
        for row in results:
            if row.sector_id not in sector_data:
                sector_data[row.sector_id] = []
            sector_data[row.sector_id].append((row.snapshot_date, row.state))

        transitions = []
        for sector_id, history in sector_data.items():
            for i in range(1, len(history)):
                prev_date, prev_state = history[i - 1]
                curr_date, curr_state = history[i]
                if prev_state != curr_state:
                    transitions.append(
                        {
                            "sector_id": sector_id,
                            "from_state": prev_state,
                            "to_state": curr_state,
                            "transition_date": curr_date,
                        }
                    )

        return transitions


# Import func for queries
from sqlalchemy.sql import func
