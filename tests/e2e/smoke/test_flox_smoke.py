"""Smoke E2E: per-agent ``flox_env`` wraps the agent argv in ``flox activate``.

A fake ``flox`` shim records that it was invoked (and with the expected
``activate -d <dir> --`` prefix) before exec'ing the wrapped agent command, so
the test proves the orchestrator actually routed the agent through Flox without
needing a real Flox install.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

import eden

pytestmark = pytest.mark.e2e


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_flox_env(root: Path) -> Path:
    manifest = root / ".flox" / "env" / "manifest.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("version = 1\n", encoding="utf-8")
    return root


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake flox/agent shims rely on POSIX executable PATH lookup + execvp",
)
def test_flox_env_wraps_agent_invocation(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    env_dir = _make_flox_env(tmp_path / "agent-env")
    marker = tmp_path / "flox-ran.txt"

    # Fake agent: ignore args, emit the completion signal, exit 0.
    _write_exe(
        bin_dir / "fakeagent",
        f"#!{sys.executable}\nprint('<promise>COMPLETE</promise>')\n",
    )

    # Fake flox: assert it was called as ``activate -d <env_dir> -- <cmd...>``,
    # record the marker, then exec the wrapped command so the agent still runs.
    _write_exe(
        bin_dir / "flox",
        "\n".join(
            [
                f"#!{sys.executable}",
                "import os, sys",
                "argv = sys.argv[1:]",
                "assert argv[0] == 'activate', argv",
                "assert argv[1] == '-d', argv",
                f"assert argv[2] == {str(env_dir)!r}, argv",
                "sep = argv.index('--')",
                f"open({str(marker)!r}, 'w').write(' '.join(argv[sep + 1:]))",
                "rest = argv[sep + 1:]",
                "os.execvp(rest[0], rest)",
            ]
        )
        + "\n",
    )

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = eden.run(
        agent=eden.cli_agent(name="fake", model="m", binary="fakeagent", flox_env=env_dir),
        sandbox=__import__("eden.sandboxes.no_sandbox", fromlist=["provider"]).provider(),
        prompt="do the thing",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    # The flox shim ran and the wrapped command was the fake agent.
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").startswith("fakeagent")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake agent shim relies on POSIX executable PATH lookup",
)
def test_flox_env_missing_manifest_fails_fast(
    e2e_git_repo: Path,
    tmp_path: Path,
) -> None:
    bare = tmp_path / "no-flox-here"
    bare.mkdir()
    with pytest.raises(eden.FloxEnvError):
        eden.run(
            agent=eden.cli_agent(name="fake", model="m", binary="fakeagent", flox_env=bare),
            sandbox=__import__("eden.sandboxes.no_sandbox", fromlist=["provider"]).provider(),
            prompt="x",
            max_iterations=1,
            completion_signal="<promise>COMPLETE</promise>",
            idle_timeout=10.0,
        )
