# -*- coding: utf-8 -*-
"""
Macro event repository for Phase 0.5 macro layer.

Stores manually-entered macro events that trigger temporary adjustments
to the macro_multiplier.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.sector_logic.db_schema import MacroEventModel

logger = logging.getLogger(__name__)


class MacroEventRepo:
    """Repository for macro_events table."""

    def add_event(self, event_type: str, direction: str, adjustment_value: float,
                  effective_date: date, expiry_date: Optional[date] = None) -> int:
        """Add a macro event. Returns the new event ID."""
        from src.storage import engine
        with Session(engine) as session:
            event = MacroEventModel(
                event_type=event_type,
                direction=direction,
                adjustment_value=adjustment_value,
                effective_date=effective_date,
                expiry_date=expiry_date,
                is_active=True,
                created_at=datetime.now(),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            logger.info(f"[MacroEventRepo] Added event: {event_type}, adjustment={adjustment_value}")
            return event.id

    def get_active_events(self) -> List[MacroEventModel]:
        """Get all active macro events."""
        from src.storage import engine
        with Session(engine) as session:
            today = date.today()
            stmt = (
                select(MacroEventModel)
                .where(MacroEventModel.is_active == True)
                .where(MacroEventModel.effective_date <= today)
                .order_by(MacroEventModel.effective_date.desc())
            )
            return session.scalars(stmt).all()

    def get_total_adjustment(self) -> float:
        """Sum all active adjustment values."""
        events = self.get_active_events()
        total = sum(e.adjustment_value for e in events if e.is_active)
        return round(total, 4)

    def clear_all_active(self) -> int:
        """Deactivate all active events. Returns count cleared."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = update(MacroEventModel).where(MacroEventModel.is_active == True).values(is_active=False)
            result = session.execute(stmt)
            session.commit()
            count = result.rowcount
            logger.info(f"[MacroEventRepo] Cleared {count} active events")
            return count
