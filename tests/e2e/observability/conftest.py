"""Shared observability test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


@pytest.fixture
def captured_spans() -> Iterator[InMemorySpanExporter]:
    """Set up an in-memory exporter for span assertions."""
    current = trace.get_tracer_provider()
    if not isinstance(current, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        # eden.tracing binds _TRACER at import time, so reload dependent
        # modules that captured the prior _TRACER reference.
        import importlib

        import eden.lifecycle._runner
        import eden.providers._impl.http_rest
        import eden.tracing as eden_tracing

        loop_module = importlib.import_module("eden.orchestrator.loop._run_loop")
        importlib.reload(eden_tracing)
        importlib.reload(loop_module)
        importlib.reload(eden.lifecycle._runner)
        importlib.reload(eden.providers._impl.http_rest)
    else:
        provider = current

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    try:
        yield exporter
    finally:
        # Drain any pending spans into the exporter, then drop it. The
        # processor itself stays attached to the provider but its exporter
        # is a per-test instance, so no spans leak across tests.
        processor.shutdown()
