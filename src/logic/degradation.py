"""LLM service degradation - health monitoring and fallback logic."""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Tuple, Callable
from decimal import Decimal
from enum import Enum

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session_maker
from src.logic.models import LogicScore, LLMServiceStatus

logger = logging.getLogger(__name__)


class LLMHealthStatus(Enum):
    """LLM service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class LLMHealthMonitor:
    """Monitor LLM service health.

    Health check mechanism:
    - Sends probe requests to LLM service
    - Tracks consecutive failures/successes
    - Determines health status based on thresholds
    """

    HEALTH_CHECK_TIMEOUT = 10  # seconds
    FAILURE_THRESHOLD = 3  # Consecutive failures before marking unhealthy
    RECOVERY_THRESHOLD = 2  # Consecutive successes before marking healthy
    SLOW_RESPONSE_THRESHOLD = 5.0  # seconds

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check_time: Optional[datetime] = None
        self.last_successful_check: Optional[datetime] = None
        self.current_status = LLMHealthStatus.HEALTHY

    async def check_health(self) -> LLMHealthStatus:
        """Check LLM service health with simple probe.

        Returns:
            LLMHealthStatus indicating service health
        """
        try:
            start_time = datetime.now()

            # Simple probe: echo test
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Respond with exactly: OK"}
                ],
                max_tokens=5,
                timeout=self.HEALTH_CHECK_TIMEOUT
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            # Check response
            content = response.choices[0].message.content.strip()
            if "OK" not in content:
                raise ValueError(f"Unexpected response: {content}")

            # Record success
            self.consecutive_failures = 0
            self.consecutive_successes += 1
            self.last_successful_check = datetime.now()

            # Determine status based on response time
            if elapsed > self.SLOW_RESPONSE_THRESHOLD:
                self.current_status = LLMHealthStatus.DEGRADED
                logger.warning(f"LLM response slow: {elapsed:.2f}s")
            elif self.consecutive_successes >= self.RECOVERY_THRESHOLD:
                self.current_status = LLMHealthStatus.HEALTHY

            self.last_check_time = datetime.now()
            return self.current_status

        except Exception as e:
            self.consecutive_successes = 0
            self.consecutive_failures += 1
            self.last_check_time = datetime.now()

            if self.consecutive_failures >= self.FAILURE_THRESHOLD:
                self.current_status = LLMHealthStatus.UNHEALTHY

            logger.warning(f"LLM health check failed ({self.consecutive_failures}/{self.FAILURE_THRESHOLD}): {e}")
            return self.current_status

    def get_status(self) -> LLMHealthStatus:
        """Get current health status without checking."""
        return self.current_status

    def is_available(self) -> bool:
        """Check if LLM is available for normal processing."""
        return self.current_status != LLMHealthStatus.UNHEALTHY

    def get_status_string(self) -> str:
        """Get status string for logging."""
        return f"{self.current_status.value} (failures={self.consecutive_failures}, successes={self.consecutive_successes})"


class DegradationService:
    """Handle LLM degradation fallback logic.

    Degradation levels:
    - FULL: Normal operation, all features available
    - DEGRADED: Slow responses, rate limited, reduced features
    - OFFLINE: Unavailable, using fallback to prior day scores
    """

    DECAY_RATE = Decimal("0.9")  # 10% daily decay for fallback

    def __init__(self):
        self.health_monitor = LLMHealthMonitor()

    async def get_logic_scores(
        self,
        target_date: date,
        llm_processor: Callable
    ) -> Tuple[Dict[str, Decimal], LLMServiceStatus]:
        """Get logic scores with degradation handling.

        Args:
            target_date: Date for scores
            llm_processor: Async callable that processes news and returns scores

        Returns:
            (scores, status) tuple
            - scores: Dict[logic_id, net_thrust]
            - status: LLMServiceStatus indicating processing mode
        """
        # Check health
        health = await self.health_monitor.check_health()

        if health == LLMHealthStatus.HEALTHY:
            # Normal processing
            try:
                scores = await llm_processor(target_date)
                return scores, LLMServiceStatus.FULL
            except Exception as e:
                logger.error(f"LLM processing failed: {e}")
                # Fall through to degraded/offline handling
                health = await self.health_monitor.check_health()

        if health == LLMHealthStatus.DEGRADED:
            # Degraded: try with reduced mode
            logger.warning("LLM degraded, attempting reduced processing")
            try:
                scores = await llm_processor(target_date, reduced_mode=True)
                return scores, LLMServiceStatus.DEGRADED
            except Exception as e:
                logger.error(f"Reduced processing failed: {e}")
                # Fall through to offline

        # Offline: use fallback
        logger.warning("LLM offline, using fallback scores")
        fallback_scores = await self._get_fallback_scores(target_date)
        return fallback_scores, LLMServiceStatus.OFFLINE

    async def _get_fallback_scores(self, target_date: date) -> Dict[str, Decimal]:
        """Get fallback scores from prior day with decay.

        Fallback logic:
        1. Fetch yesterday's logic_scores
        2. Apply 10% decay
        3. Return as fallback
        """
        prior_date = target_date - timedelta(days=1)

        async with async_session_maker() as session:
            # Fetch prior day scores
            result = await session.execute(
                select(LogicScore).where(
                    LogicScore.snapshot_date == prior_date
                )
            )
            prior_scores = result.scalars().all()

            if not prior_scores:
                logger.warning(f"No prior scores for {prior_date}, using zeros")
                return {}

            # Apply decay
            fallback = {}
            for ps in prior_scores:
                if ps.net_thrust is not None:
                    decayed = ps.net_thrust * self.DECAY_RATE
                    fallback[ps.logic_id] = decayed

            logger.info(
                f"Fallback scores computed: {len(fallback)} logics, "
                f"decay={self.DECAY_RATE}"
            )

            return fallback

    async def persist_fallback_metadata(
        self,
        scores: Dict[str, Decimal],
        snapshot_date: date,
        status: LLMServiceStatus
    ) -> None:
        """Persist fallback metadata for auditing."""
        async with async_session_maker() as session:
            for logic_id, score in scores.items():
                # Check if record exists
                existing = await session.execute(
                    select(LogicScore).where(
                        LogicScore.logic_id == logic_id,
                        LogicScore.snapshot_date == snapshot_date
                    )
                )
                existing = existing.scalar_one_or_none()

                if existing:
                    existing.llm_service_status = status
                    existing.fallback_applied = (status != LLMServiceStatus.FULL)
                    existing.fallback_reason = f"LLM {status.value} at {datetime.now()}"
                else:
                    # Create new record for fallback
                    logic_score = LogicScore(
                        logic_id=logic_id,
                        snapshot_date=snapshot_date,
                        net_thrust=score,
                        llm_service_status=status,
                        fallback_applied=(status != LLMServiceStatus.FULL),
                        fallback_reason=f"LLM {status.value} at {datetime.now()}",
                    )
                    session.add(logic_score)

            await session.commit()
