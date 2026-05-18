"""Load ``.eden/.env`` so projects can declare sandbox env without wiring dotenv themselves.

Mirrors sandcastle's ``.sandcastle/.env`` convention: any key=value pairs
declared in the project's ``.eden/.env`` are merged into the env passed to
the sandbox at ``run()`` / ``create_sandbox()`` time. Values from the file are
overridden by explicit ``env=`` keyword arguments to keep call-site overrides
predictable.

Escape sequences in double-quoted values (``\\n``, ``\\r``, ``\\t``, ``\\\\``)
are unescaped by python-dotenv, so gateway tokens with embedded newlines
forward correctly into the container.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

from eden.errors import InvalidOptions


def load_dotenv_file(path: Path) -> dict[str, str]:
    """Parse a single ``.env`` file into a ``dict[str, str]``.

    Skips entries whose values are ``None`` (bare ``KEY`` lines with no
    ``=value``) since those carry no payload to forward into the sandbox.
    Raises :class:`InvalidOptions` if the file cannot be read as text.
    """
    try:
        raw = dotenv_values(path)
    except OSError as exc:
        raise InvalidOptions(
            code="config.invalid_options",
            message=f"failed to read env file {path}: {exc}",
            hint="check the file is readable and uses UTF-8 encoding",
        ) from exc
    return {k: v for k, v in raw.items() if v is not None}


def load_eden_env(host_repo_path: Path) -> dict[str, str]:
    """Return values from ``<host_repo_path>/.eden/.env``, or ``{}`` if absent.

    The missing-file case is silent on purpose — projects opt in by creating
    the file, opt out by leaving it absent.
    """
    path = host_repo_path / ".eden" / ".env"
    if not path.is_file():
        return {}
    return load_dotenv_file(path)
