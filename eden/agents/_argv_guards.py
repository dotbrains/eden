"""Shared argv-size guards for agents that pass the prompt positionally.

Linux's execve(2) caps the total argv + envp at ARG_MAX (commonly 128 KB on
glibc systems). Agents whose CLI accepts the prompt as an argv element
(cursor's positional, copilot's ``-p <prompt>``) need a host-side check
so a too-long prompt fails fast with a clear error, rather than as a
cryptic ``OSError: [Errno 7] Argument list too long`` from the runner.

Agents that deliver the prompt via stdin (claude_code, codex) don't need
this guard — execve only sees the argv vector, not the stdin payload.
"""

from __future__ import annotations

from eden.errors import InvalidOptions

# Conservative limit. Linux's ARG_MAX is typically 131_072 bytes (128 KiB);
# upstream uses 120_000 to leave headroom for envp + other argv elements.
_MAX_PROMPT_ARGV_BYTES = 120_000


def assert_prompt_fits_argv(*, prompt: str, agent_name: str) -> None:
    """Raise ``InvalidOptions`` when the prompt would overflow ARG_MAX.

    The check compares UTF-8 byte length (what execve actually counts)
    rather than ``len(prompt)`` so high-codepoint prompts are sized
    correctly.
    """
    n = len(prompt.encode("utf-8"))
    if n > _MAX_PROMPT_ARGV_BYTES:
        raise InvalidOptions(
            code="config.prompt_too_long",
            message=(
                f"{agent_name} prompt is {n:,} bytes; the Linux execve argv "
                f"limit caps this at ~{_MAX_PROMPT_ARGV_BYTES:,}. "
                "Trim the prompt, reference long context via files, or use "
                "an agent that delivers the prompt via stdin (claude_code, codex)."
            ),
            hint="see eden/agents/_argv_guards.py for the size constant",
        )


__all__ = ["assert_prompt_fits_argv"]
