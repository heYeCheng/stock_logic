"""Logic layer module - LLM-driven event extraction and scorecard rule engine."""

# Import models first to register tables with Base.metadata
from src.logic.models import (
    LogicModel,
    EventModel,
    LogicScore,
    LogicDirection,
    ImportanceLevel,
    LLMServiceStatus,
)

# Import services after models to avoid circular imports
from src.logic.llm_service import LogicIdentificationService
from src.logic.event_extractor import EventExtractionService
from src.logic.scorecard import EventScorecard, ScorecardManager
from src.logic.fingerprint import EventFingerprintService
from src.logic.net_thrust import NetThrustCalculator, LogicSnapshotService
from src.logic.degradation import LLMHealthMonitor, DegradationService

__all__ = [
    # Models
    "LogicModel",
    "EventModel",
    "LogicScore",
    "LogicDirection",
    "ImportanceLevel",
    "LLMServiceStatus",
    # Services
    "LogicIdentificationService",
    "EventExtractionService",
    "EventScorecard",
    "ScorecardManager",
    "EventFingerprintService",
    "NetThrustCalculator",
    "LogicSnapshotService",
    "LLMHealthMonitor",
    "DegradationService",
]
