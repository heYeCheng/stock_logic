# -*- coding: utf-8 -*-
"""
EventBus: internal event bus for sector logic events.

Subscribers register handlers for event types:
- logic_flip (HIGH priority)
- risk_alert (MEDIUM priority)
- analysis_complete (LOW priority)

Usage:
    event_bus.subscribe("logic_flip", handler_fn)
    await event_bus.publish("logic_flip", {"event": flip_event_dict})
"""

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    """
    Internal event bus (sync/async handler calls).
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.info(f"[EventBus] subscribed handler to {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    async def publish(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            logger.debug(f"[EventBus] no subscribers for {event_type}")
            return

        logger.info(f"[EventBus] publishing {event_type} to {len(handlers)} handlers")
        for handler in handlers:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"[EventBus] handler error for {event_type}: {e}")

    async def publish_flip_event(self, flip_event: Dict[str, Any]) -> None:
        """Publish a logic flip event (HIGH priority)."""
        await self.publish("logic_flip", {
            "event": flip_event,
            "priority": "HIGH",
        })

    async def publish_risk_alert(self, risk_alert: Dict[str, Any]) -> None:
        """Publish a risk alert event (MEDIUM priority)."""
        await self.publish("risk_alert", {
            "event": risk_alert,
            "priority": "MEDIUM",
        })

    async def publish_analysis_complete(self, result: Dict[str, Any]) -> None:
        """Publish analysis complete event (LOW priority)."""
        await self.publish("analysis_complete", {
            "event": result,
            "priority": "LOW",
        })

    def get_subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))

    def list_event_types(self) -> List[str]:
        """List all event types with subscribers."""
        return list(self._subscribers.keys())
