"""Structural validation of action.yml — the GitHub Action manifest.

Catches drift between ``eden run``'s CLI flags and the inputs the action
forwards to it. The action is a composite GHA so we don't actually run a
workflow here; we just verify the manifest is well-formed and the input
names line up with ``eden run``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.repo_checks._paths import repo_root

pytestmark = pytest.mark.unit


def _action_path() -> Path:
    return repo_root() / "action.yml"


def _load_action() -> dict[str, object]:
    """Parse action.yml without bringing PyYAML in as a runtime dep.

    PyYAML is not in eden's dependency tree; this test does a tiny
    hand-rolled parse of the keys we care about (top-level fields and
    `inputs` sub-keys), which is enough for the structural checks here.
    """
    text = _action_path().read_text(encoding="utf-8")
    out: dict[str, object] = {}
    inputs: dict[str, dict[str, str]] = {}
    section: str | None = None
    current_input: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            # top-level key
            key, _, value = line.partition(":")
            section = key.strip()
            value = value.strip()
            if section == "inputs":
                out["inputs"] = inputs
                current_input = None
            elif value:
                out[section] = value.strip('"')
        elif section == "inputs":
            stripped = line.strip()
            if line.startswith("  ") and not line.startswith("    "):
                # input name
                current_input = stripped.rstrip(":")
                inputs[current_input] = {}
            elif current_input is not None:
                k, _, v = stripped.partition(":")
                inputs[current_input][k.strip()] = v.strip().strip('"')
    return out


def test_action_yml_exists() -> None:
    assert _action_path().is_file(), "action.yml missing at repo root"


def test_action_has_name_and_description() -> None:
    parsed = _load_action()
    assert "name" in parsed
    assert "description" in parsed
    name = parsed["name"]
    assert isinstance(name, str) and "eden" in name.lower()


def test_action_inputs_match_eden_run_flags() -> None:
    """Every action input must correspond to either an `eden run` flag or
    to GHA-only metadata (python-version, eden-version) the action handles
    itself before calling eden."""
    parsed = _load_action()
    inputs = parsed.get("inputs")
    assert isinstance(inputs, dict)

    # Inputs that map to `eden run` flags. Hyphenated input names map to
    # the `--<input>` flag the action passes through.
    expected_run_flags = {
        "template",
        "sandbox",
        "agent",
        "model",
        "backlog",
        "image-name",
        "max-iterations",
        "idle-timeout",
        "completion-timeout",
    }
    # Inputs that the action handles before reaching `eden run`.
    expected_meta = {"python-version", "eden-version"}

    declared = set(inputs.keys())
    extras = declared - (expected_run_flags | expected_meta)
    missing = expected_run_flags - declared
    assert not extras, f"unexpected inputs: {sorted(extras)}"
    assert not missing, f"missing run-flag inputs: {sorted(missing)}"


def test_action_is_composite() -> None:
    """The action must be `runs.using: composite` so it works on any runner
    without docker (matrix CI) and forwards env vars from the caller."""
    text = _action_path().read_text(encoding="utf-8")
    assert 'using: "composite"' in text
