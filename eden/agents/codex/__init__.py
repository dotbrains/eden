"""OpenAI Codex CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from eden.agents.codex._agent import _CodexAgent
from eden.agents.codex._argv import Effort


def codex(
    model: str = "gpt-5",
    *,
    name: str = "codex",
    effort: Effort | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_bypass_approvals_and_sandbox: bool = True,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> _CodexAgent:
    """OpenAI Codex CLI agent.

    Builds the invocation::

        codex exec [resume <id>] --json
              [--dangerously-bypass-approvals-and-sandbox]
              -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]

    with the prompt delivered via stdin.

    Args:
        model: Default ``"gpt-5"`` is illustrative — override per call site.
        name: Agent identifier (default ``"codex"``).
        effort: Optional reasoning-effort level. When set, threads
            ``-c model_reasoning_effort="<level>"`` into the invocation.
            One of ``"low"``, ``"medium"``, ``"high"``, ``"xhigh"``.
        env: Per-agent environment additions (merged by the orchestrator).
        capture_sessions: When ``True``, the orchestrator post-processes each
            iteration's session JSONL into ``.eden/sessions/...`` via
            :class:`CodexSessionStorage`. Default ``True``.
        dangerously_bypass_approvals_and_sandbox: When ``True``, appends
            ``--dangerously-bypass-approvals-and-sandbox`` so codex does not
            block on per-tool approval prompts. Safe inside an isolated
            sandbox; think twice before enabling for ``no_sandbox()``.
            Default ``True``.
        extra_args: Escape hatch for unsurfaced codex CLI flags. Appended
            after the standard flags.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs
            codex inside it via ``flox activate -d <dir> -- <argv>``. Enforced
            when present: a missing manifest or ``flox`` binary raises
            ``FloxEnvError`` (set ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).

    The agent's ``parse_stream`` decodes codex JSONL events
    (``thread.started`` → ``session_id``, ``item.completed``/``agent_message``
    → ``text``, ``item.started``/``command_execution`` → ``tool_call`` (Bash),
    ``error`` → ``text``).
    """
    from eden.session._codex import CodexSessionStorage

    return _CodexAgent(
        name=name,
        model=model,
        captures_sessions=capture_sessions,
        _effort=effort,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        _dangerously_bypass_approvals_and_sandbox=dangerously_bypass_approvals_and_sandbox,
        _session_storage=CodexSessionStorage() if capture_sessions else None,
        flox_env=flox_env,
    )


__all__ = ["codex"]
