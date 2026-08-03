"""Unit tests for in-process request latency samples."""

from __future__ import annotations

from platform_api.services.request_latency import latency_summary, record_latency_ms


def test_progress_latency_percentile() -> None:
    for value in (10.0, 20.0, 30.0, 40.0, 100.0):
        record_latency_ms("/progress-test", value)
    summary = latency_summary("/progress-test")
    assert summary["samples"] == 5
    assert summary["p50_ms"] == 30.0
    assert summary["p95_ms"] is not None
    assert summary["max_ms"] == 100.0
