"""E2E: OpenTelemetry metrics derived from spans.

Each ``span()`` context manager bumps a counter and records a duration
histogram named after the span. The test installs an
``InMemoryMetricReader`` so we can inspect what gets emitted.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
)

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


@pytest.fixture
def captured_metrics() -> Iterator[InMemoryMetricReader]:
    """Install a MeterProvider with an in-memory reader and reload eden modules
    so they rebind the meter. Mirrors the fixture pattern used for tracing.
    """
    current = metrics.get_meter_provider()
    if not isinstance(current, MeterProvider):
        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)
        # Force-reload eden.tracing so its module-level meter rebinds to the
        # provider just installed. Then reload modules that captured the prior
        # span/_counter/_histogram references.
        import eden.lifecycle._runner
        import eden.orchestrator._loop
        import eden.providers._impl.http_rest
        import eden.tracing as eden_tracing

        importlib.reload(eden_tracing)
        importlib.reload(eden.orchestrator._loop)
        importlib.reload(eden.lifecycle._runner)
        importlib.reload(eden.providers._impl.http_rest)
    else:
        # Fixture already initialized in-process; pull the existing reader off
        # of the provider via its internal slot. There's no public accessor,
        # but the test only ever installs the provider once per session, so
        # we cache the reader on the provider for later fetches.
        reader = current._fixture_reader  # type: ignore[attr-defined]

    if not hasattr(current, "_fixture_reader"):
        # First-time init: stash for later tests in the same session. The
        # SDK's MeterProvider is a subclass of the API's MeterProvider, so
        # this attribute lives on the concrete instance.
        active = metrics.get_meter_provider()
        active._fixture_reader = reader  # type: ignore[attr-defined]

    yield reader


def _names(reader: InMemoryMetricReader) -> list[str]:
    """Return all metric names visible in the reader's current snapshot."""
    data = reader.get_metrics_data()
    if data is None:
        return []
    out: list[str] = []
    for resource_metric in data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                out.append(metric.name)
    return out


def test_run_emits_run_count_and_duration(
    e2e_git_repo: Path, captured_metrics: InMemoryMetricReader
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
    )
    names = _names(captured_metrics)
    assert "eden.run.count" in names
    assert "eden.run.duration_seconds" in names


def test_agent_exec_metric_names(
    e2e_git_repo: Path, captured_metrics: InMemoryMetricReader
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
    )
    names = _names(captured_metrics)
    # Spans wired in eden/orchestrator/_loop.py and eden/lifecycle/_runner.py
    # all auto-derive metrics through eden/tracing/__init__.py's span().
    for expected in (
        "eden.sandbox.create.count",
        "eden.agent.exec.count",
        "eden.agent.exec.duration_seconds",
    ):
        assert expected in names, f"missing metric: {expected!r}; got {names}"
