"""Shared stubs for create_sandbox tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from eden.providers._types import BranchStrategy, CreateOptions, ExecResult


@dataclass
class StubHandle:
    worktree_path: Path
    closed: list[bool] = field(default_factory=lambda: [False])
    exec_calls: list[dict[str, object]] = field(default_factory=list)
    exec_results: list[ExecResult] = field(default_factory=list)

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        self.exec_calls.append(
            {
                "cmd": cmd,
                "on_line": on_line,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
                "stdin": stdin,
            }
        )
        if on_line is not None:
            on_line("line")
        if self.exec_results:
            return self.exec_results.pop(0)
        return ExecResult(stdout="ok", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        self.closed[0] = True


@dataclass
class StubProvider:
    name: str = "stub"
    kind: Literal["bind_mount", "isolated", "none"] = "bind_mount"
    supported: frozenset[str] = field(
        default_factory=lambda: frozenset({"head", "merge_to_head", "named"})
    )
    seen_opts: list[CreateOptions] = field(default_factory=list)

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self.supported

    def create(self, opts: CreateOptions) -> Any:
        self.seen_opts.append(opts)
        return StubHandle(worktree_path=opts.worktree_path)
