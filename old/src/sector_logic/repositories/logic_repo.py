# -*- coding: utf-8 -*-
"""
Logic repository for Phase 0.5 logic engine.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from src.sector_logic.db_schema import LogicModel

logger = logging.getLogger(__name__)


class LogicRepo:
    """Repository for sector_logic_logics table."""

    def save(self, logic_id: str, sector_code: str, title: str, description: str,
             direction: str, category: str, importance_level: str,
             initial_strength: float, evidence_summary: Optional[str] = None,
             catalyst_events: Optional[list] = None) -> None:
        """Save or update a logic."""
        from src.storage import engine
        with Session(engine) as session:
            existing = session.get(LogicModel, logic_id)
            if existing:
                existing.title = title
                existing.description = description
                existing.direction = direction
                existing.category = category
                existing.importance_level = importance_level
                existing.initial_strength = initial_strength
                existing.is_active = True
                existing.updated_at = datetime.now()
            else:
                logic = LogicModel(
                    logic_id=logic_id,
                    sector_code=sector_code,
                    title=title,
                    description=description,
                    direction=direction,
                    category=category,
                    importance_level=importance_level,
                    initial_strength=initial_strength,
                    current_strength=initial_strength,
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(logic)
            session.commit()
            logger.debug(f"[LogicRepo] Saved logic: {logic_id}")

    def get_by_sector(self, sector_code: str, active_only: bool = True) -> List[LogicModel]:
        """Get all logics for a sector."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = select(LogicModel).where(LogicModel.sector_code == sector_code)
            if active_only:
                stmt = stmt.where(LogicModel.is_active == True)
            stmt = stmt.order_by(LogicModel.initial_strength.desc())
            return session.scalars(stmt).all()

    def get_by_id(self, logic_id: str) -> Optional[LogicModel]:
        """Get a single logic by ID."""
        from src.storage import engine
        with Session(engine) as session:
            return session.get(LogicModel, logic_id)

    def update_strength(self, logic_id: str, new_strength: float) -> None:
        """Update current_strength."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = update(LogicModel).where(LogicModel.logic_id == logic_id).values(
                current_strength=new_strength,
                updated_at=datetime.now(),
            )
            session.execute(stmt)
            session.commit()

    def update_last_event(self, logic_id: str, event_date: date) -> None:
        """Update last_event_date and increment count."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = update(LogicModel).where(LogicModel.logic_id == logic_id).values(
                last_event_date=event_date,
                last_event_count=LogicModel.last_event_count + 1,
                updated_at=datetime.now(),
            )
            session.execute(stmt)
            session.commit()

    def deactivate(self, logic_id: str) -> None:
        """Mark a logic as inactive."""
        from src.storage import engine
        with Session(engine) as session:
            stmt = update(LogicModel).where(LogicModel.logic_id == logic_id).values(
                is_active=False,
                updated_at=datetime.now(),
            )
            session.execute(stmt)
            session.commit()

    def to_dict(self, logic: LogicModel) -> dict:
        """Convert LogicModel to dict."""
        return {
            'logic_id': logic.logic_id,
            'sector_code': logic.sector_code,
            'title': logic.title,
            'description': logic.description,
            'direction': logic.direction,
            'category': logic.category,
            'importance_level': logic.importance_level,
            'initial_strength': logic.initial_strength,
            'current_strength': logic.current_strength,
            'is_active': logic.is_active,
            'last_event_date': logic.last_event_date.isoformat() if logic.last_event_date else None,
            'last_event_count': logic.last_event_count,
        }
