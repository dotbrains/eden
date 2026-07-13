"""E2E: OpenTelemetry tracing on the iteration loop and the REST client.

Uses the OTel SDK's in-memory span exporter to assert eden emits the spans
documented in ADR 0012. Without an SDK installed, eden code paths run
unchanged via OTel's NoOpTracer — this test deliberately wires up the SDK
so we can inspect what gets emitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from eden.agents import simulated_agent
from eden.lifecycle import Hook, Hooks, HostHooks
from eden.orchestrator import run
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_run_emits_run_span(e2e_git_repo: Path, captured_spans: InMemorySpanExporter) -> None:
    run(
        agent=simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
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
    run(
        agent=simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
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
    run(
        agent=simulated_agent(output="x\n"),  # no completion → 2 iterations
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=2,
        completion_signal="NEVER",
        idle_timeout=10.0,
    )
    exec_spans = [s for s in captured_spans.get_finished_spans() if s.name == "eden.agent.exec"]
    assert len(exec_spans) == 2
    indexes = sorted(int((s.attributes or {})["iteration.index"]) for s in exec_spans)  # type: ignore[arg-type]
    assert indexes == [0, 1]


def test_hook_emits_eden_hook_span(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    hooks = Hooks(
        host=HostHooks(on_worktree_ready=(Hook(cmd="true"),)),
    )
    run(
        agent=simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
        hooks=hooks,
    )
    hook_spans = [s for s in captured_spans.get_finished_spans() if s.name == "eden.hook"]
    assert hook_spans, "no eden.hook spans captured"
    attrs = dict(hook_spans[0].attributes or {})
    assert attrs["hook.location"] == "host"
    assert attrs["hook.command"] == "true"
    assert attrs["hook.phase"] == "on_worktree_ready"


def test_run_span_records_completion_signal_attribute(
    e2e_git_repo: Path, captured_spans: InMemorySpanExporter
) -> None:
    run(
        agent=simulated_agent(output="x\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=3,
        idle_timeout=10.0,
    )
    run_span = next(s for s in captured_spans.get_finished_spans() if s.name == "eden.run")
    attrs = dict(run_span.attributes or {})
    assert attrs["completion_signal"] == "<promise>COMPLETE</promise>"
