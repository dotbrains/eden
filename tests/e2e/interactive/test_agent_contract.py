"""E2E: interactive agent command and prompt behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_interactive_uses_build_interactive_command_when_present(
    e2e_git_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """If the agent defines build_interactive_command, eden uses it."""
    out_dir = tmp_path_factory.mktemp("interactive-log")
    log_file = out_dir / "log.txt"
    log_file.touch()

    class _Probe:
        name = "probe"
        model = "x"

        def build_command(self, ctx: IterationContext) -> list[str]:
            return [sys.executable, "-c", f"open({str(log_file)!r}, 'w').write('build_command')"]

        def build_interactive_command(self, ctx: IterationContext) -> list[str]:
            return [
                sys.executable,
                "-c",
                f"open({str(log_file)!r}, 'w').write('build_interactive_command')",
            ]

        def parse_stream(self, _line: str) -> None:  # pragma: no cover - unused here
            return None

    eden.interactive(agent=_Probe(), sandbox=no_sandbox())
    assert log_file.read_text() == "build_interactive_command"


def test_interactive_renders_prompt_substitutions(e2e_git_repo: Path, tmp_path: Path) -> None:
    """Agent receives a rendered prompt via build_interactive_command(ctx)."""
    seen: list[str] = []

    class _Probe:
        name = "probe"
        model = "x"

        def build_interactive_command(self, ctx: IterationContext) -> list[str]:
            seen.append(ctx.prompt)
            return [sys.executable, "-c", "import sys; sys.exit(0)"]

        def build_command(self, ctx: IterationContext) -> list[str]:  # pragma: no cover
            return self.build_interactive_command(ctx)

        def parse_stream(self, _line: str) -> None:  # pragma: no cover
            return None

    eden.interactive(
        agent=_Probe(),
        sandbox=no_sandbox(),
        prompt="branch={{SOURCE_BRANCH}}",
    )
    assert len(seen) == 1
    assert seen[0].startswith("branch=")
