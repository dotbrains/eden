"""Per-agent Flox runtime activation (ADR-0014).

Each agent factory may declare a ``flox_env`` directory containing a
``.flox/env/manifest.toml``. When set, the orchestrator wraps the agent's argv
in ``flox activate -d <dir> -- <argv...>`` so the agent CLI runs inside its own
declared, lockfile-pinned toolchain instead of inheriting the host's.

Enforced when present (mirrors blacksmith's ``validateFloxEnv``): a declared env
whose manifest is missing, or a missing ``flox`` binary, raises
:class:`~eden.errors.FloxEnvError`. The ``EDEN_ALLOW_NO_FLOX=1`` escape hatch
(analogous to blacksmith's ``BLACKSMITH_ALLOW_NO_FLOX``) skips activation when
``flox`` is unavailable, for Windows / CI smoke tests.

Agents that do not declare a ``flox_env`` are unchanged: ``flox_wrap`` returns
the argv untouched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from eden.errors import FloxEnvError

ALLOW_NO_FLOX_ENV = "EDEN_ALLOW_NO_FLOX"
_MANIFEST_RELPATH = Path(".flox") / "env" / "manifest.toml"


def _allow_no_flox() -> bool:
    """True when ``EDEN_ALLOW_NO_FLOX`` is set to a truthy value."""
    return os.environ.get(ALLOW_NO_FLOX_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def validate_flox_env(flox_env: str | Path) -> Path:
    """Resolve ``flox_env`` and require its Flox manifest to exist.

    Returns the resolved directory. Raises :class:`FloxEnvError` when the
    directory has no ``.flox/env/manifest.toml`` — the same dangling-reference
    failure blacksmith refuses to register.
    """
    env_dir = Path(flox_env).expanduser()
    manifest = env_dir / _MANIFEST_RELPATH
    if not manifest.is_file():
        raise FloxEnvError(
            message=(
                f"agent declares flox_env {str(flox_env)!r} but no Flox manifest "
                f"exists at {manifest}"
            ),
            hint=(
                "point flox_env at a directory containing .flox/env/manifest.toml "
                "(run `flox init` there), or drop the flox_env declaration"
            ),
        )
    return env_dir


def flox_wrap(
    argv: list[str],
    *,
    flox_env: str | Path | None,
    flox_bin: str = "flox",
) -> list[str]:
    """Wrap ``argv`` so it runs inside the agent's declared Flox env.

    Returns ``argv`` unchanged when ``flox_env`` is ``None``. Otherwise validates
    the env (see :func:`validate_flox_env`) and returns
    ``[flox_bin, "activate", "-d", <dir>, "--", *argv]``.

    Raises :class:`FloxEnvError` when ``flox`` is not on ``PATH``, unless
    ``EDEN_ALLOW_NO_FLOX`` is set — in which case the original ``argv`` is
    returned so callers without Flox (Windows / CI) still run.
    """
    if flox_env is None:
        return argv
    env_dir = validate_flox_env(flox_env)
    if shutil.which(flox_bin) is None:
        if _allow_no_flox():
            return argv
        raise FloxEnvError(
            message=(
                f"agent declares flox_env {str(flox_env)!r} but the {flox_bin!r} "
                "binary was not found on PATH"
            ),
            hint=(
                "install Flox (https://flox.dev) so the env can be activated, or "
                f"set {ALLOW_NO_FLOX_ENV}=1 to run without it"
            ),
        )
    return [flox_bin, "activate", "-d", str(env_dir), "--", *argv]


__all__ = ["ALLOW_NO_FLOX_ENV", "flox_wrap", "validate_flox_env"]
