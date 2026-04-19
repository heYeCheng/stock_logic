# -*- coding: utf-8 -*-
"""
Event repository for Phase 0.5 event scoreboard.

Stores and queries events for the logic scoring system.
Uses the project's existing SQLite storage pattern.
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy import and_, func, select, delete
from sqlalchemy.orm import Session

from src.storage import get_db_context
from src.sector_logic.db_schema import EventModel

logger = logging.getLogger(__name__)


class EventRepo:
    """Repository for sector_logic_events table."""

    def add_event(self, logic_id: str, event_type: str, direction: str,
                  score_impact: float, event_date: date, expire_date: date,
                  summary: str, event_hash: str) -> bool:
        """
        Add an event. Returns True if inserted, False if duplicate.
        Uses INSERT OR IGNORE on unique constraint for dedup.
        """
        try:
            from src.storage import engine
            with Session(engine) as session:
                event = EventModel(
                    logic_id=logic_id,
                    event_type=event_type,
                    direction=direction,
                    score_impact=score_impact,
                    event_date=event_date,
                    expire_date=expire_date,
                    summary=summary,
                    event_hash=event_hash,
                    created_at=datetime.now(),
                )
                session.add(event)
                session.commit()
                logger.debug(f"[EventRepo] Added event: logic_id={logic_id}, type={event_type}")
                return True
        except Exception as e:
            if "UNIQUE constraint" in str(e) or "UNIQUE" in str(e).upper():
                logger.debug(f"[EventRepo] Duplicate event skipped: logic_id={logic_id}, hash={event_hash[:8]}")
                return False
            logger.error(f"[EventRepo] Failed to add event: {e}")
            raise

    def get_valid_events(self, logic_id: str, current_date: date) -> List[EventModel]:
        """Get all valid (non-expired) events for a logic as of current_date."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = (
                select(EventModel)
                .where(EventModel.logic_id == logic_id)
                .where(EventModel.expire_date >= current_date)
                .order_by(EventModel.event_date)
            )
            return session.scalars(stmt).all()

    def get_events_by_date_range(self, logic_id: str, start: date, end: date) -> List[EventModel]:
        """Get events for a logic within a date range."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = (
                select(EventModel)
                .where(EventModel.logic_id == logic_id)
                .where(EventModel.event_date >= start)
                .where(EventModel.event_date <= end)
                .order_by(EventModel.event_date.desc())
            )
            return session.scalars(stmt).all()

    def count_events(self, logic_id: str) -> int:
        """Count total events for a logic."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = select(func.count()).select_from(EventModel).where(EventModel.logic_id == logic_id)
            return session.scalar(stmt) or 0
