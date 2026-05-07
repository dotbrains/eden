"""E2E: OpenTelemetry tracing on the iteration loop and the REST client.

Uses the OTel SDK's in-memory span exporter to assert eden emits the spans
documented in ADR 0012. Without an SDK installed, eden code paths run
unchanged via OTel's NoOpTracer — this test deliberately wires up the SDK
so we can inspect what gets emitted.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


@pytest.fixture
def captured_spans() -> Iterator[InMemorySpanExporter]:
    """Set up an in-memory exporter for span assertions.

    OTel only allows ``set_tracer_provider`` to succeed once per process —
    subsequent calls are silently ignored. The fixture installs a real
    :class:`TracerProvider` on first use (reloading eden modules so they
    rebind ``_TRACER``), and on later runs reuses that provider, attaching
    a fresh in-memory exporter as a span processor for the duration of the
    test. Each test only sees its own spans because each gets its own
    exporter.
    """
    current = trace.get_tracer_provider()
    if not isinstance(current, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        # eden.tracing binds _TRACER at import time — reload so it picks
        # up the freshly-installed provider, then reload modules that
        # captured the prior _TRACER reference.
        import importlib

        import eden.lifecycle._runner
        import eden.orchestrator._loop
        import eden.providers._impl.http_rest
        import eden.tracing as eden_tracing

        importlib.reload(eden_tracing)
        importlib.reload(eden.orchestrator._loop)
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


def test_run_emits_run_span(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
    )
    spans = captured_spans.get_finished_spans()
    names = [s.name for s in spans]
    assert "eden.run" in names

    run_span = next(s for s in spans if s.name == "eden.run")
    attrs = dict(run_span.attributes or {})
    assert attrs["agent.name"] == "simulated"
    assert attrs["sandbox.name"] == "no_sandbox"
    assert attrs["sandbox.kind"] == "bind_mount"
    assert attrs["max_iterations"] == 1
    assert attrs["completion_signal"] == "<promise>COMPLETE</promise>"
    assert attrs["iterations"] == 1


def test_run_emits_sandbox_create_and_agent_exec_spans(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
    )
    names = [s.name for s in captured_spans.get_finished_spans()]
    assert "eden.sandbox.create" in names
    assert "eden.agent.exec" in names


def test_agent_exec_span_carries_iteration_index(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="x\n"),  # no completion → 2 iterations
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=2,
        completion_signal="NEVER",
        idle_timeout=10.0,
    )
    exec_spans = [
        s for s in captured_spans.get_finished_spans() if s.name == "eden.agent.exec"
    ]
    assert len(exec_spans) == 2
    indexes = sorted(int((s.attributes or {})["iteration.index"]) for s in exec_spans)  # type: ignore[arg-type]
    assert indexes == [0, 1]


def test_hook_emits_eden_hook_span(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    hooks = eden.Hooks(
        host=eden.HostHooks(on_worktree_ready=(eden.Hook(cmd="true"),)),
    )
    eden.run(
        agent=eden.simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
        hooks=hooks,
    )
    hook_spans = [
        s for s in captured_spans.get_finished_spans() if s.name == "eden.hook"
    ]
    assert hook_spans, "no eden.hook spans captured"
    attrs = dict(hook_spans[0].attributes or {})
    assert attrs["hook.location"] == "host"
    assert attrs["hook.command"] == "true"
    assert attrs["hook.phase"] == "on_worktree_ready"


def test_rest_client_emits_request_span(
    captured_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RestClient emits an eden.rest.request span with method/url/status."""
    from unittest.mock import MagicMock

    import requests

    from eden.providers._impl.http_rest import RestClient

    client = RestClient(
        base_url="https://api.test/",
        headers={"Authorization": "Bearer test"},
        timeout=5.0,
        max_retries=0,
    )

    def fake_request(*a: object, **kw: object) -> MagicMock:
        m = MagicMock(spec=requests.Response)
        m.status_code = 200
        m.headers = {}
        m.text = '{"ok": true}'
        m.json.return_value = {"ok": True}
        return m

    monkeypatch.setattr(client._session, "request", fake_request)
    client.get("/api/x")

    rest_spans = [
        s for s in captured_spans.get_finished_spans() if s.name == "eden.rest.request"
    ]
    assert rest_spans, "no eden.rest.request span captured"
    attrs = dict(rest_spans[0].attributes or {})
    assert attrs["http.method"] == "GET"
    assert attrs["http.url"] == "https://api.test/api/x"
    assert attrs["http.status_code"] == 200
    assert attrs["http.retry_count"] == 0


def test_run_span_records_completion_signal_attribute(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    eden.run(
        agent=eden.simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=3,
        idle_timeout=10.0,
    )
    run_span = next(
        s for s in captured_spans.get_finished_spans() if s.name == "eden.run"
    )
    attrs = dict(run_span.attributes or {})
    assert attrs["completion_signal"] == "<promise>COMPLETE</promise>"
