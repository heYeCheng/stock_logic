"""Catalyst service for stock catalyst marker determination."""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .models import StockCatalyst
from src.logic.models import EventModel


class CatalystService:
    """Determine stock catalyst markers based on recent events.

    Classification logic:
    - strong: 2 or more high-importance events
    - medium: 1 high-importance event
    - none: No high-importance events
    """

    LOOKBACK_DAYS = 5  # Look back 5 days for events

    def determine_catalyst(
        self,
        events: List[EventModel]
    ) -> str:
        """Determine catalyst level from events.

        Args:
            events: Recent events affecting this stock

        Returns:
            "strong" | "medium" | "none"

        Classification:
            - strong: 2+ high-importance events
            - medium: 1 high-importance event
            - none: No high-importance events
        """
        if not events:
            return "none"

        # Count high-importance events
        # Assuming events have importance_level attribute
        high_count = sum(
            1 for e in events if getattr(e, 'importance_level', None) == "high"
        )

        if high_count >= 2:
            return "strong"
        elif high_count == 1:
            return "medium"
        else:
            return "none"

    def _build_description(
        self,
        events: List[EventModel],
        catalyst: str
    ) -> str:
        """Build brief catalyst description.

        Args:
            events: Recent events affecting this stock
            catalyst: Catalyst level ("strong"/"medium"/"none")

        Returns:
            Brief description string
        """
        if catalyst == "none":
            return "无显著催化剂"

        # Get unique logic names
        logic_names = list(set(
            e.logic_name for e in events if hasattr(e, 'logic_name') and e.logic_name
        ))

        if catalyst == "strong":
            return f"多重高重要性事件驱动：{', '.join(logic_names[:3])}" if logic_names else "多重高重要性事件驱动"
        else:
            return f"重要事件驱动：{', '.join(logic_names[:3])}" if logic_names else "重要事件驱动"

    async def generate_catalyst(
        self,
        session: AsyncSession,
        stock_code: str,
        snapshot_date: date,
        stock_events: List[EventModel]
    ) -> StockCatalyst:
        """Generate catalyst marker for a stock.

        Args:
            session: Database session
            stock_code: Stock code to generate catalyst for
            snapshot_date: Date for the snapshot
            stock_events: Recent events affecting this stock

        Returns:
            StockCatalyst record
        """
        # Determine catalyst
        catalyst = self.determine_catalyst(stock_events)

        # Count events
        high_count = sum(
            1 for e in stock_events if getattr(e, 'importance_level', None) == "high"
        )

        # Build description
        description = self._build_description(stock_events, catalyst)

        # Create record
        record = StockCatalyst(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            catalyst_level=catalyst,
            event_count=len(stock_events),
            high_importance_count=high_count,
            description=description
        )

        # Persist
        session.add(record)
        await session.commit()

        return record

    async def get_stock_events(
        self,
        session: AsyncSession,
        stock_code: str,
        start_date: date,
        end_date: date
    ) -> List[EventModel]:
        """Get recent events affecting a stock.

        Args:
            session: Database session
            stock_code: Stock code to get events for
            start_date: Start of lookback window
            end_date: End of lookback window

        Returns:
            List of EventModel records

        Note: This requires a stock-logic mapping to determine which events
        affect which stocks. Implementation depends on STOCK-01 (stock-sector
        mapping) and logic-stock relationships.
        """
        # For now, this is a placeholder that would be implemented
        # once stock-logic mapping is available
        # The actual implementation would query events through
        # stock -> sector -> logic -> events relationship
        return []
