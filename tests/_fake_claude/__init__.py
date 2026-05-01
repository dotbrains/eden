"""Install a fake `claude` executable for e2e tests."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from tests._fake_claude._transcript import Transcript


def install_fake_claude(
    *,
    tmp_dir: Path,
    transcript: Transcript,
    session_id: str,
    sandbox_cwd: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Write a Python script named `claude` to ``tmp_dir`` and prepend its
    parent directory to PATH. Override $HOME (and USERPROFILE on Windows) to
    a fresh tmp tree.

    Side effects:
        - Writes the executable to <tmp_dir>/bin/claude (no extension).
        - Writes a session JSONL to <tmp_dir>/home/.claude/projects/<slug>/<id>.jsonl.
        - Sets $PATH to put <tmp_dir>/bin first.
        - Sets $HOME (and USERPROFILE) to <tmp_dir>/home.

    Returns the home dir Path so callers can introspect the captured file.
    """
    bin_dir = tmp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_dir / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    # Pre-write the Claude session JSONL the shim will reference.
    # Slug derivation matches eden.session._slug.claude_projects_slug:
    # replace /, \, : with - and rstrip trailing dashes.
    slug = sandbox_cwd.replace("/", "-").replace("\\", "-").replace(":", "-")
    slug = slug.rstrip("-")
    session_dir = home_dir / ".claude" / "projects" / slug
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{session_id}.jsonl"
    session_file.write_text(
        transcript.session_jsonl_body(sandbox_cwd=sandbox_cwd),
        encoding="utf-8",
    )

    # Stream-json lines emitted by the shim, in order.
    lines = transcript.stream_json_lines()
    script_path = bin_dir / "claude"
    script_path.write_text(
        "\n".join(
            [
                f"#!{sys.executable}",
                "import sys, time",
                "lines = " + repr(lines),
                "for line in lines:",
                "    sys.stdout.write(line + '\\n')",
                "    sys.stdout.flush()",
                "    time.sleep(0.01)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))

    return home_dir


__all__ = ["Transcript", "install_fake_claude"]
