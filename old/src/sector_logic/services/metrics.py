# -*- coding: utf-8 -*-
"""
SectorLogicMetrics: metrics collection for sector logic analysis.

Collects counters, histograms, and gauges for monitoring and observability.

Usage:
    metrics = SectorLogicMetrics()
    metrics.record_sector_analysis("AI/算力", "产业趋势", 0.72, 1234)
    metrics.record_flip_event("dominant_collapse")
    print(metrics.summary())
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Counter:
    """Simple counter for tracking event counts."""

    def __init__(self):
        self._counts: Dict[str, int] = defaultdict(int)

    def inc(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._make_key(name, labels)
        self._counts[key] += 1

    def get(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        return self._counts.get(self._make_key(name, labels), 0)

    def all(self) -> Dict[str, int]:
        return dict(self._counts)

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name


class Histogram:
    """Simple histogram for tracking duration distributions."""

    def __init__(self):
        self._observations: Dict[str, List[float]] = defaultdict(list)

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._make_key(name, labels)
        self._observations[key].append(value)

    def get_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        key = self._make_key(name, labels)
        values = self._observations.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name


class Gauge:
    """Simple gauge for tracking current values."""

    def __init__(self):
        self._values: Dict[str, float] = {}

    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._make_key(name, labels)
        self._values[key] = value

    def get(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        return self._values.get(self._make_key(name, labels))

    def all(self) -> Dict[str, float]:
        return dict(self._values)

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name


class SectorLogicMetrics:
    """
    Metrics collection for sector logic analysis.
    """

    def __init__(self):
        self.counters = Counter()
        self.histograms = Histogram()
        self.gauges = Gauge()

    # Collection metrics
    def record_collection_duration(self, collector: str, duration_ms: float) -> None:
        self.histograms.observe("collection_duration_ms", duration_ms, {"collector": collector})
        self.counters.inc("collection_total", {"collector": collector})

    def record_collection_success(self, collector: str, target_count: int) -> None:
        self.counters.inc("collection_success_total", {"collector": collector})
        self.gauges.set("collection_targets", target_count, {"collector": collector})

    def record_collection_failure(self, collector: str, target: str, error: str) -> None:
        self.counters.inc("collection_failure_total", {"collector": collector})
        logger.warning(f"[Metrics] collection failed: collector={collector}, target={target}, error={error}")

    # Analysis metrics
    def record_analysis_duration(self, date_str: str, duration_ms: float) -> None:
        self.histograms.observe("analysis_duration_ms", duration_ms, {"date": date_str})

    def record_sector_analysis(
        self, sector: str, logic_category: str, strength: float, duration_ms: float
    ) -> None:
        self.counters.inc("sector_analysis_total", {"sector": sector, "category": logic_category})
        self.histograms.observe("sector_analysis_duration_ms", duration_ms, {"sector": sector})
        self.gauges.set("sector_logic_strength", strength, {"sector": sector})

    # LLM metrics
    def record_llm_call(self, module: str, success: bool, duration_ms: float) -> None:
        self.counters.inc("llm_call_total", {"module": module, "success": str(success)})
        self.histograms.observe("llm_call_duration_ms", duration_ms, {"module": module})

    # Event metrics
    def record_flip_event(self, flip_type: str) -> None:
        self.counters.inc("flip_event_total", {"flip_type": flip_type})

    def record_risk_alert(self, risk_factor: str) -> None:
        self.counters.inc("risk_alert_total", {"risk_factor": risk_factor})

    # Macro metrics
    def record_macro_state(self, state: str, score: float) -> None:
        self.gauges.set("macro_thesis_score", score)
        self.counters.inc("macro_evaluation_total", {"state": state})

    # Lifecycle metrics
    def record_lifecycle_transition(
        self, sector: str, from_stage: str, to_stage: str
    ) -> None:
        self.counters.inc(
            "lifecycle_transition_total",
            {"sector": sector, "from": from_stage, "to": to_stage},
        )

    def summary(self) -> Dict[str, Any]:
        """Generate a summary of all metrics."""
        return {
            "counters": self.counters.all(),
            "histograms": {
                "analysis_duration": self.histograms.get_stats("analysis_duration_ms"),
                "sector_analysis_duration": self.histograms.get_stats("sector_analysis_duration_ms"),
                "llm_call_duration": self.histograms.get_stats("llm_call_duration_ms"),
            },
            "gauges": self.gauges.all(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters = Counter()
        self.histograms = Histogram()
        self.gauges = Gauge()
