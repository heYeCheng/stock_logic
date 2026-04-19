"""Event fingerprint service - generates fingerprints and detects duplicates."""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import EventModel

logger = logging.getLogger(__name__)


class EventFingerprintService:
    """Generate and validate event fingerprints for deduplication.

    Fingerprint is a SHA256 hash of canonical event fields:
    - source: News source identifier
    - event_date: Date when event occurred
    - logic_id: Associated logic
    - headline_prefix: First 50 chars of headline

    Deduplication window: 24 hours
    """

    DEDUP_WINDOW_HOURS = 24

    def generate_fingerprint(
        self,
        source: str,
        event_date: datetime,
        logic_id: str,
        headline: str
    ) -> str:
        """Generate unique fingerprint for event.

        Args:
            source: News source identifier
            event_date: Event date
            logic_id: Associated logic ID
            headline: Event headline

        Returns:
            64-character hex string (SHA256)
        """
        # Normalize headline (remove whitespace variations)
        headline_normalized = " ".join(headline.split())
        headline_prefix = headline_normalized[:50]

        # Create canonical string
        canonical = f"{source}|{event_date.strftime('%Y-%m-%d')}|{logic_id}|{headline_prefix}"

        # Generate SHA256 hash
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()

        logger.debug(f"Generated fingerprint: {fingerprint[:16]}... for {logic_id}")
        return fingerprint

    async def is_duplicate(
        self,
        fingerprint: str,
        event_date: datetime
    ) -> bool:
        """Check if event with same fingerprint exists within dedup window.

        Args:
            fingerprint: Pre-computed fingerprint
            event_date: Date of the event

        Returns:
            True if duplicate found within 24-hour window
        """
        async with async_session_maker() as session:
            window_start = event_date - timedelta(hours=self.DEDUP_WINDOW_HOURS)
            window_end = event_date + timedelta(hours=self.DEDUP_WINDOW_HOURS)

            result = await session.execute(
                select(EventModel).where(
                    EventModel.fingerprint == fingerprint,
                    EventModel.event_date >= window_start,
                    EventModel.event_date <= window_end
                )
            )

            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"Duplicate detected: {fingerprint[:16]}...")
                return True

            return False

    async def find_cross_source_duplicate(
        self,
        logic_id: str,
        event_date: datetime,
        headline: str
    ) -> Optional[EventModel]:
        """Find duplicate from different source.

        Some events are reported by multiple sources.
        We want to keep the one with highest strength.

        Args:
            logic_id: Associated logic ID
            event_date: Event date
            headline: Event headline

        Returns:
            Existing event if found, None otherwise
        """
        async with async_session_maker() as session:
            # Fuzzy match: same logic_id, same date, similar headline prefix
            headline_prefix = headline[:30]

            result = await session.execute(
                select(EventModel).where(
                    EventModel.logic_id == logic_id,
                    EventModel.event_date == event_date.date(),
                    EventModel.headline.like(f"{headline_prefix}%")
                )
            )

            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"Cross-source duplicate found: {existing.event_id}")
                return existing

            return None

    def should_replace(
        self,
        existing: EventModel,
        new_strength: float
    ) -> bool:
        """Determine if new event should replace existing.

        Keep the event with higher strength_raw.

        Args:
            existing: Existing event
            new_strength: New event's strength_raw

        Returns:
            True if new event should replace existing
        """
        existing_strength = float(existing.strength_raw) if existing.strength_raw else 0
        return new_strength > existing_strength
