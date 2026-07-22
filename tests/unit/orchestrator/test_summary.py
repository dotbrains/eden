"""Verify the run-summary formatters."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden._types import Commit, Iteration, Usage
from eden.agents import simulated_agent
from eden.errors import StructuredOutputError
from eden.orchestrator._result import assemble_loop_result
from eden.orchestrator._summary import (
    context_window_k,
    format_context_window_line,
    format_finalize_line,
)
from eden.output import Output
from eden.providers._types import FinalizeResult
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.unit


def _u(input_t: int, cc: int = 0, cr: int = 0, output: int = 0) -> Usage:
    return Usage(
        input_tokens=input_t,
        cache_creation_input_tokens=cc,
        cache_read_input_tokens=cr,
        output_tokens=output,
    )


def test_zero_input_returns_zero_k() -> None:
    assert context_window_k(_u(0)) == 0
    assert format_context_window_line(_u(0)) == "Context window: 0k"


def test_sums_input_cache_creation_and_cache_read() -> None:
    assert context_window_k(_u(50_000, cc=20_000, cr=30_000)) == 100


def test_rounds_up_to_nearest_1000() -> None:
    assert context_window_k(_u(1)) == 1
    assert context_window_k(_u(1001)) == 2
    assert context_window_k(_u(999)) == 1
    assert context_window_k(_u(50_500)) == 51


def test_output_tokens_excluded() -> None:
    """Output tokens are not part of the next-call context window."""
    assert context_window_k(_u(50_000, output=999_999)) == 50


def test_format_line_shape() -> None:
    assert format_context_window_line(_u(50_000)) == "Context window: 50k"
    assert format_context_window_line(_u(99_999, cc=1, cr=0, output=0)) == "Context window: 100k"


def _fr(*, applied: bool, n_files: int, bytes_: int) -> FinalizeResult:
    files: tuple[Path, ...] = tuple(Path(f"f{i}.py") for i in range(n_files))
    return FinalizeResult(applied=applied, files_changed=files, patch_size_bytes=bytes_)


def test_finalize_line_no_changes() -> None:
    assert format_finalize_line(_fr(applied=True, n_files=0, bytes_=0)) == (
        "[eden] no changes to sync"
    )


def test_finalize_line_single_file_pluralization() -> None:
    assert format_finalize_line(_fr(applied=True, n_files=1, bytes_=42)) == (
        "[eden] syncing 1 file to host (42 bytes)"
    )


def test_finalize_line_multiple_files_pluralization() -> None:
    assert format_finalize_line(_fr(applied=True, n_files=3, bytes_=128)) == (
        "[eden] syncing 3 files to host (128 bytes)"
    )


def test_finalize_line_partial_failure() -> None:
    assert format_finalize_line(_fr(applied=False, n_files=2, bytes_=64)) == (
        "[eden] sync incomplete: 2 files attempted (64 bytes)"
    )


def test_structured_output_error_carries_commits_from_loop_result() -> None:
    commits = [Commit(sha="abc123")]
    with pytest.raises(StructuredOutputError) as ex:
        assemble_loop_result(
            iterations=[
                Iteration(
                    index=0,
                    completion_signal=None,
                    session_id="sess-1",
                    session_file_path=None,
                    usage=None,
                )
            ],
            completion_signal=None,
            branch="eden/test",
            stdout="<result>not json</result>",
            worktree_path=Path("/tmp/worktree"),
            preserved_worktree_path=None,
            cwd=Path("/tmp/repo"),
            prompt="<result>",
            env={},
            log_file_path=None,
            commits=commits,
            output=Output.object(tag="result", schema=lambda raw: raw),
            agent=simulated_agent(),
            sandbox=no_sandbox(),
        )

    assert ex.value.commits == commits
    assert ex.value.session_id == "sess-1"
