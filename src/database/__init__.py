"""Database module - MySQL connection pool and ORM models."""

from src.database.connection import engine, async_session_maker, Base, get_async_session
from src.database.models import StockModel, MarketDataModel, MacroSnapshot

# Logic layer models - lazy import to avoid circular imports
# Import them here for backward compatibility
__all__ = [
    "engine",
    "async_session_maker",
    "Base",
    "get_async_session",
    "StockModel",
    "MarketDataModel",
    "MacroSnapshot",
    # Lazy imports below
]


def __getattr__(name):
    """Lazy imports for LogicModel, EventModel, LogicScore."""
    if name in ("LogicModel", "EventModel", "LogicScore"):
        from src.logic.models import LogicModel, EventModel, LogicScore
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
