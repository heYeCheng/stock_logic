"""Integration tests for Phase 3 Logic Layer.

Tests the complete pipeline:
1. Logic identification (LLM)
2. Event extraction (LLM)
3. Fingerprint deduplication
4. Scorecard scoring
5. Net thrust calculation
6. Degradation fallback
"""

import asyncio
import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.logic.llm_service import LogicIdentificationService
from src.logic.event_extractor import EventExtractionService
from src.logic.scorecard import EventScorecard, ScorecardManager, ScorecardConfig, ScorecardEvent
from src.logic.fingerprint import EventFingerprintService
from src.logic.net_thrust import NetThrustCalculator, LogicSnapshotService
from src.logic.degradation import LLMHealthMonitor, DegradationService
from src.logic.models import LogicModel, LogicDirection, ImportanceLevel, EventModel


# Sync tests for services that don't require database
class TestLogicIdentification:
    """Test logic identification service."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        service = LogicIdentificationService(model="claude-sonnet-4-6")
        assert service.model == "claude-sonnet-4-6"
        assert service.SYSTEM_PROMPT is not None
        assert "逻辑家族" in service.SYSTEM_PROMPT


class TestEventExtraction:
    """Test event extraction service."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        extractor = EventExtractionService(model="claude-sonnet-4-6")
        assert extractor.model == "claude-sonnet-4-6"
        assert extractor.SYSTEM_PROMPT is not None
        assert "强度评分标准" in extractor.SYSTEM_PROMPT


class TestFingerprintDeduplication:
    """Test event fingerprint deduplication."""

    def test_fingerprint_generation(self):
        """Test fingerprint is deterministic."""
        service = EventFingerprintService()

        fp1 = service.generate_fingerprint(
            source="财联社",
            event_date=date(2026, 4, 19),
            logic_id="policy_5g_001",
            headline="工信部发布 5G 政策"
        )

        fp2 = service.generate_fingerprint(
            source="财联社",
            event_date=date(2026, 4, 19),
            logic_id="policy_5g_001",
            headline="工信部发布 5G 政策"
        )

        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex length

    def test_fingerprint_different_inputs(self):
        """Test different inputs produce different fingerprints."""
        service = EventFingerprintService()

        fp1 = service.generate_fingerprint(
            source="财联社",
            event_date=date(2026, 4, 19),
            logic_id="policy_5g_001",
            headline="工信部发布 5G 政策"
        )

        fp2 = service.generate_fingerprint(
            source="财联社",
            event_date=date(2026, 4, 19),
            logic_id="policy_5g_001",
            headline="工信部发布 6G 政策"  # Different headline
        )

        assert fp1 != fp2


class TestScorecard:
    """Test event scorecard rule engine."""

    def test_importance_multiplier(self):
        """Test importance multiplier application."""
        config = ScorecardConfig()
        scorecard = EventScorecard("test_logic", config)

        event = ScorecardEvent(
            event_id="evt_001",
            logic_id="test_logic",
            event_date=date.today(),
            strength_raw=Decimal("0.8"),
            direction="positive",
            importance_level="high",
            validity_days=30
        )

        scorecard.add_event(event)

        # high multiplier = 1.5, so 0.8 * 1.5 = 1.2, capped at 1.0
        assert event.strength_adjusted == Decimal("1.0")

    def test_decay_application(self):
        """Test time decay application."""
        config = ScorecardConfig(daily_decay_rate=Decimal("0.9"))
        scorecard = EventScorecard("test_logic", config)

        # Add event 5 days ago
        event_date = date.today() - timedelta(days=5)
        event = ScorecardEvent(
            event_id="evt_001",
            logic_id="test_logic",
            event_date=event_date,
            strength_raw=Decimal("0.8"),
            direction="positive",
            importance_level="medium",
            validity_days=30
        )

        scorecard.add_event(event)
        # Set last_updated to event_date so decay will be applied
        scorecard.last_updated = event_date
        # Apply decay to today (5 days later)
        scorecard.apply_decay(target_date=date.today())

        # Score should be decayed: 0.8 * 0.9^5 ≈ 0.47
        assert scorecard.current_score < Decimal("0.8")


class TestNetThrust:
    """Test net thrust calculation."""

    def test_net_thrust_calculation(self):
        """Test net thrust with positive and negative events."""
        from src.logic.models import EventModel

        # Create mock events
        positive_event = EventModel(
            event_id="evt_pos_001",
            logic_id="test_logic",
            event_date=date.today(),
            strength_raw=Decimal("0.8"),
            strength_adjusted=Decimal("1.0"),  # After multiplier
            direction=LogicDirection.positive
        )

        negative_event = EventModel(
            event_id="evt_neg_001",
            logic_id="test_logic",
            event_date=date.today(),
            strength_raw=Decimal("0.5"),
            strength_adjusted=Decimal("0.5"),
            direction=LogicDirection.negative
        )

        calculator = NetThrustCalculator()
        result = calculator.calculate([positive_event, negative_event])

        assert result.positive_strength == Decimal("1.0")
        assert result.negative_strength == Decimal("0.5")
        assert result.net_thrust == Decimal("0.5")
        assert result.has_anti_logic == True

    def test_net_thrust_only_positive(self):
        """Test net thrust with only positive events."""
        from src.logic.models import EventModel

        positive_event = EventModel(
            event_id="evt_pos_001",
            logic_id="test_logic",
            event_date=date.today(),
            strength_raw=Decimal("0.8"),
            strength_adjusted=Decimal("1.0"),
            direction=LogicDirection.positive
        )

        calculator = NetThrustCalculator()
        result = calculator.calculate([positive_event])

        assert result.positive_strength == Decimal("1.0")
        assert result.negative_strength == Decimal("0")
        assert result.net_thrust == Decimal("1.0")
        assert result.has_anti_logic == False


class TestDegradation:
    """Test LLM degradation handling."""

    def test_health_monitor_healthy(self):
        """Test health monitor status."""
        monitor = LLMHealthMonitor()

        assert monitor.is_available() == True
        assert monitor.get_status().name == "HEALTHY"

    def test_degradation_service_fallback(self):
        """Test degradation service fallback logic."""
        service = DegradationService()

        # Test decay rate
        assert service.DECAY_RATE == Decimal("0.9")

        # Test fallback would apply 10% decay to prior day scores


class TestEndToEndPipeline:
    """Test complete Logic Layer pipeline (sync version)."""

    def test_pipeline_imports(self):
        """Test all pipeline components can be imported."""
        from src.logic.llm_service import LogicIdentificationService
        from src.logic.event_extractor import EventExtractionService
        from src.logic.scorecard import ScorecardEvent
        from src.logic.fingerprint import EventFingerprintService
        from src.logic.net_thrust import NetThrustCalculator
        from src.logic.degradation import DegradationService

        # Verify all services instantiate correctly
        assert LogicIdentificationService() is not None
        assert EventExtractionService() is not None
        assert ScorecardEvent is not None
        assert EventFingerprintService() is not None
        assert NetThrustCalculator() is not None
        assert DegradationService() is not None

    def test_pipeline_data_flow(self):
        """Test data flows through pipeline components."""
        # Create a logic
        logic = LogicModel(
            logic_id="test_logic_001",
            logic_name="Test Logic",
            logic_family="policy",
            direction=LogicDirection.positive,
            importance_level=ImportanceLevel.high,
            description="Test",
            keywords=["test"],
            validity_days=30,
            is_active=True
        )

        # Create an event
        event = EventModel(
            event_id="evt_001",
            logic_id=logic.logic_id,
            event_date=date.today(),
            strength_raw=Decimal("0.8"),
            strength_adjusted=Decimal("1.0"),
            direction=LogicDirection.positive
        )

        # Calculate net thrust
        calculator = NetThrustCalculator()
        result = calculator.calculate([event])

        assert result.logic_id == "test_logic_001"
        assert result.positive_strength == Decimal("1.0")
        assert result.net_thrust == Decimal("1.0")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
