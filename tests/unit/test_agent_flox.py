"""Per-agent Flox runtime: argv wrapping + validation + factory wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.agents._flox import ALLOW_NO_FLOX_ENV, flox_wrap, validate_flox_env
from eden.errors import ConfigError, FloxEnvError

pytestmark = pytest.mark.unit


def _make_env(root: Path) -> Path:
    """Create a directory with a minimal ``.flox/env/manifest.toml`` and return it."""
    manifest = root / ".flox" / "env" / "manifest.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('version = 1\n[install]\ngit.pkg-path = "git"\n', encoding="utf-8")
    return root


def test_flox_wrap_noop_when_unset() -> None:
    argv = ["claude", "--model", "m", "-p", "-"]
    assert flox_wrap(argv, flox_env=None) is argv


def test_validate_flox_env_returns_dir(tmp_path: Path) -> None:
    env = _make_env(tmp_path / "env")
    assert validate_flox_env(env) == env


def test_validate_flox_env_rejects_missing_manifest(tmp_path: Path) -> None:
    bare = tmp_path / "no-flox"
    bare.mkdir()
    with pytest.raises(FloxEnvError) as ei:
        validate_flox_env(bare)
    assert "no Flox manifest exists" in str(ei.value)
    assert ei.value.code == "config.flox_env"
    # Enforced-when-present failures are configuration errors.
    assert isinstance(ei.value, ConfigError)


def test_flox_wrap_wraps_when_flox_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path / "env")
    monkeypatch.setattr("eden.agents._flox.shutil.which", lambda _bin: "/usr/bin/flox")
    argv = ["claude", "-p", "-"]
    wrapped = flox_wrap(argv, flox_env=env)
    assert wrapped == ["flox", "activate", "-d", str(env), "--", "claude", "-p", "-"]


def test_flox_wrap_raises_when_flox_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_env(tmp_path / "env")
    monkeypatch.setattr("eden.agents._flox.shutil.which", lambda _bin: None)
    monkeypatch.delenv(ALLOW_NO_FLOX_ENV, raising=False)
    with pytest.raises(FloxEnvError) as ei:
        flox_wrap(["claude"], flox_env=env)
    assert "not found on PATH" in str(ei.value)


def test_flox_wrap_bypassed_by_escape_hatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_env(tmp_path / "env")
    monkeypatch.setattr("eden.agents._flox.shutil.which", lambda _bin: None)
    monkeypatch.setenv(ALLOW_NO_FLOX_ENV, "1")
    argv = ["claude", "-p", "-"]
    # No flox binary, but the escape hatch returns the argv unchanged.
    assert flox_wrap(argv, flox_env=env) == argv


def test_factories_store_flox_env(tmp_path: Path) -> None:
    env = _make_env(tmp_path / "env")
    agents = [
        eden.claude_code(model="m", flox_env=env),
        eden.codex(flox_env=env),
        eden.opencode(flox_env=env),
        eden.pi(flox_env=env),
        eden.cursor(flox_env=env),
        eden.copilot(flox_env=env),
        eden.cli_agent(name="x", model="m", binary="b", flox_env=env),
    ]
    for agent in agents:
        # Read via getattr: ``flox_env`` is a duck-typed attribute, not part of
        # the ``Agent`` Protocol (matching how the orchestrator reads it).
        assert getattr(agent, "flox_env", None) == env
