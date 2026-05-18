"""Verify .eden/.env loading: parser, lookup, and escape-sequence handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.env import load_dotenv_file, load_eden_env
from eden.errors import InvalidOptions

pytestmark = pytest.mark.unit


def test_load_dotenv_file_parses_simple_pairs(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("FOO=bar\nBAZ=qux\n")
    assert load_dotenv_file(f) == {"FOO": "bar", "BAZ": "qux"}


def test_load_dotenv_file_unescapes_double_quoted_sequences(tmp_path: Path) -> None:
    # python-dotenv handles \n, \r, \t, \\ inside double-quoted values — the
    # gateway-token case from sandcastle PR #568.
    f = tmp_path / ".env"
    f.write_text('TOKEN="line1\\nline2"\nTAB="a\\tb"\nSLASH="x\\\\y"\n')
    values = load_dotenv_file(f)
    assert values["TOKEN"] == "line1\nline2"
    assert values["TAB"] == "a\tb"
    assert values["SLASH"] == "x\\y"


def test_load_dotenv_file_single_quoted_is_literal(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("RAW='no\\nescape'\n")
    assert load_dotenv_file(f) == {"RAW": "no\\nescape"}


def test_load_dotenv_file_skips_bare_keys(tmp_path: Path) -> None:
    # ``BARE`` with no ``=value`` parses to None — drop it since there's no
    # payload to forward into the sandbox.
    f = tmp_path / ".env"
    f.write_text("BARE\nSET=ok\n")
    assert load_dotenv_file(f) == {"SET": "ok"}


def test_load_dotenv_file_missing_raises(tmp_path: Path) -> None:
    # dotenv_values silently returns {} for missing files; load_dotenv_file
    # is the lower-level helper for callers that have a known path — we let
    # OSError bubble through InvalidOptions only for actual IO failures.
    # A missing file via load_dotenv_file currently returns {} (matches
    # python-dotenv behaviour); the public ``load_eden_env`` is the
    # missing-file no-op contract.
    assert load_dotenv_file(tmp_path / "does-not-exist.env") == {}


def test_load_eden_env_missing_returns_empty(tmp_path: Path) -> None:
    assert load_eden_env(tmp_path) == {}


def test_load_eden_env_directory_at_path_returns_empty(tmp_path: Path) -> None:
    # Defensive: if ``.eden/.env`` is somehow a directory, treat as absent
    # rather than raising — keeps the auto-load path opt-in by file presence.
    eden_dir = tmp_path / ".eden" / ".env"
    eden_dir.mkdir(parents=True)
    assert load_eden_env(tmp_path) == {}


def test_load_eden_env_reads_dot_eden_env(tmp_path: Path) -> None:
    eden_dir = tmp_path / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("ANTHROPIC_API_KEY=sk-test\nLOG_LEVEL=debug\n")
    assert load_eden_env(tmp_path) == {
        "ANTHROPIC_API_KEY": "sk-test",
        "LOG_LEVEL": "debug",
    }


def test_load_dotenv_file_unreadable_raises_invalid_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = tmp_path / ".env"
    f.write_text("FOO=bar\n")

    def _explode(*_args: object, **_kwargs: object) -> dict[str, str | None]:
        raise OSError("simulated read failure")

    monkeypatch.setattr("eden.env._dotenv.dotenv_values", _explode)
    with pytest.raises(InvalidOptions) as excinfo:
        load_dotenv_file(f)
    assert "failed to read env file" in excinfo.value.message
