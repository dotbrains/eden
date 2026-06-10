"""pi CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.pi._stream import parse_line as _parse_line
from eden.errors import InvalidOptions
from eden.streaming import StreamEvent

if TYPE_CHECKING:
    from eden.session._pi import PiSessionStorage

_NAME = "pi"

PiThinking = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
_VALID_THINKING: tuple[str, ...] = ("off", "minimal", "low", "medium", "high", "xhigh")


@dataclass(frozen=True)
class _PiAgent:
    name: str
    model: str
    captures_sessions: bool
    _binary: str = "pi"
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _session_storage: PiSessionStorage | None = None
    flox_env: str | Path | None = None

    @property
    def session_storage(self) -> PiSessionStorage | None:
        return self._session_storage

    def build_command(self, ctx: IterationContext) -> list[str]:
        return [self._binary, *self._extra_args, ctx.prompt]

    def parse_stream(self, line: str) -> StreamEvent | None:
        return _parse_line(line, agent_name=self.name, iteration=0)


def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
    thinking: PiThinking | None = None,
    capture_sessions: bool = True,
    flox_env: str | Path | None = None,
) -> Agent:
    """pi CLI agent. Assumes `pi` binary is on PATH.

    Default `model` ("pi-3.5") is illustrative — override via the positional
    `model` argument or supply your own `extra_args` for binary-specific flags.

    ``thinking`` forwards ``--thinking <level>`` to the pi CLI. Accepted
    levels: ``"off"``, ``"minimal"``, ``"low"``, ``"medium"``, ``"high"``,
    ``"xhigh"``. Mirrors upstream's ``pi("model", { thinking: "high" })``
    option (v0.6.6, 1201b4d).

    ``capture_sessions`` toggles session capture / resume support. When
    ``True`` (default), each iteration's JSONL is copied into
    ``.eden/sessions/<branch>/iter-<i>-<id>.jsonl`` and can be resumed
    via ``run(..., resume_session=<id>)``. Mirrors upstream's
    ``PiOptions.captureSessions`` (v0.6.6, 932aa70).

    ``flox_env``, when set to a directory containing a Flox env
    (``.flox/env/manifest.toml``), runs pi inside it via
    ``flox activate -d <dir> -- <argv>``. Enforced when present: a missing
    manifest or ``flox`` binary raises ``FloxEnvError`` (set
    ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).

    The agent's ``parse_stream`` decodes pi JSONL events (``session`` →
    session_id, ``message_update`` / ``text_delta``,
    ``tool_execution_start`` for known tools (``Bash``, ``WebSearch``,
    ``WebFetch``, ``Agent``), ``agent_end``, ``agent_error`` / ``error``)
    so live display and file logs see structured text / tool_call events
    instead of one-line-per-token noise.
    """
    if thinking is not None and thinking not in _VALID_THINKING:
        raise InvalidOptions(
            code="config.invalid_options",
            message=f"pi(thinking={thinking!r}) invalid; must be one of {list(_VALID_THINKING)}",
        )
    merged_extra_args: tuple[str, ...] = (
        ("--thinking", thinking, *extra_args) if thinking is not None else tuple(extra_args)
    )
    session_storage = None
    if capture_sessions:
        from eden.session._pi import PiSessionStorage

        session_storage = PiSessionStorage()
    return _PiAgent(
        name=_NAME,
        model=model,
        captures_sessions=capture_sessions,
        _env=dict(env) if env is not None else {},
        _extra_args=merged_extra_args,
        _session_storage=session_storage,
        flox_env=flox_env,
    )


__all__ = ["PiThinking", "pi"]
