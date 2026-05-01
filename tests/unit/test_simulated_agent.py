"""Verify simulated_agent factory."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext, simulated_agent
from eden.providers._types import ExecResult


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...

    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...

    def close(self) -> None: ...


pytestmark = pytest.mark.unit


def _ctx(iteration: int = 0, prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=iteration,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/tmp/x"),
        branch="HEAD",
        name=None,
    )


def test_default_metadata() -> None:
    a = simulated_agent()
    assert a.name == "simulated"
    assert a.model == "deterministic-1"


def test_custom_name_and_model() -> None:
    a = simulated_agent(name="fixture", model="v9")
    assert a.name == "fixture"
    assert a.model == "v9"


def test_build_command_argv_runs_and_emits_output() -> None:
    a = simulated_agent(output="hello\n<promise>COMPLETE</promise>\n")
    argv = a.build_command(_ctx())
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "hello" in proc.stdout
    assert "<promise>COMPLETE</promise>" in proc.stdout


def test_output_callable_per_iteration() -> None:
    def producer(ctx: IterationContext) -> str:
        return f"iter={ctx.iteration} prompt={ctx.prompt}\n"

    a = simulated_agent(output=producer)
    argv = a.build_command(_ctx(iteration=2, prompt="hi"))
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert "iter=2" in proc.stdout
    assert "prompt=hi" in proc.stdout


def test_output_list_emits_lines_in_order() -> None:
    a = simulated_agent(output=["line-A", "line-B", "<promise>COMPLETE</promise>"])
    argv = a.build_command(_ctx())
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    out_lines = [line for line in proc.stdout.splitlines() if line]
    assert out_lines == ["line-A", "line-B", "<promise>COMPLETE</promise>"]


def test_fail_with_raises_on_build_command() -> None:
    a = simulated_agent(fail_with=RuntimeError("nope"))
    with pytest.raises(RuntimeError, match="nope"):
        a.build_command(_ctx())


def test_parse_stream_returns_none_so_orchestrator_wraps_text() -> None:
    a = simulated_agent()
    assert a.parse_stream("any line") is None


def test_delay_per_line_drives_idle_paths() -> None:
    """delay_per_line => argv that prints with sleep between lines.

    We just check the argv carries a delay marker; the actual sleep is exercised
    in the orchestrator's idle-watchdog tests.
    """
    a = simulated_agent(output=["a", "b"], delay_per_line=0.05)
    argv = a.build_command(_ctx())
    joined = " ".join(argv)
    assert "0.05" in joined
