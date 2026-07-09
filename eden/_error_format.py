"""Centralized formatter for surface-friendly error messages.

Eden's error taxonomy spans three sub-packages:

* ``eden.errors`` — top-level ``EdenError`` subclasses (config, agent, REST,
  hooks, timeouts, structured output, session capture).
* ``eden.sandboxes.errors`` — ``SandboxError`` family (provider-unavailable,
  image-not-found, exec failures, mount config).
* ``eden.worktree.errors`` — git worktree problems.

Every concrete error already attaches a structured ``code`` and a
human-readable ``message``; many already carry a ``hint``. There is
value in *one* place that consults all of them and returns a single
display string with a friendlier prefix.

This module provides that. CLI surfaces (``eden run``, REPL drivers,
custom orchestrators) can route any ``EdenError`` through
:func:`format_error_message` to get something the user can act on:

    >>> try:
    ...     eden.run(...)
    ... except EdenError as e:
    ...     print(format_error_message(e))

The mapping is conservative: when an error already has a ``hint``, we
preserve it; we only synthesise hints for tag families that don't yet
carry one (notably ``ProviderUnavailable``, ``ImageNotFound``,
``ContainerStartFailed``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eden._error_hints import provider_hint, worktree_hint
from eden.errors import (
    Aborted,
    AgentError,
    ConfigError,
    CopyToWorktreeError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    IdleTimeout,
    PromptError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
    SessionCaptureFailed,
    StepTimeout,
    StructuredOutputError,
)

if TYPE_CHECKING:
    pass


def _has_attr(obj: object, name: str) -> bool:
    return getattr(obj, name, None) is not None


def _code_of(error: EdenError) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code:
        return code
    # Errors in eden.sandboxes.errors / eden.worktree.errors don't carry a
    # `code` attr; fall back to the class name.
    return error.__class__.__name__


def _message_of(error: EdenError) -> str:
    msg = getattr(error, "message", None)
    if isinstance(msg, str) and msg:
        return msg
    # Fall through to str(error) for SandboxError / WorktreeError, which
    # build their text in ``super().__init__(...)`` rather than carrying
    # ``message``.
    return str(error) or error.__class__.__name__


def _hint_of(error: EdenError) -> str | None:
    raw = getattr(error, "hint", None)
    return raw if isinstance(raw, str) and raw else None


def _kind_prefix(error: EdenError) -> str:
    """Return a short noun phrase for the error class.

    The prefix is rendered in front of the message so users can scan a
    log and identify what failed without reading the code string.
    """
    # Most-specific subclasses first.
    if isinstance(error, RestAuthError):
        return "Authentication failed"
    if isinstance(error, RestNotFoundError):
        return "Resource not found"
    if isinstance(error, RestRateLimited):
        return "Rate limit hit"
    if isinstance(error, RestError):
        return "REST request failed"
    if isinstance(error, IdleTimeout):
        return "Agent went idle"
    if isinstance(error, StepTimeout):
        return "Iteration step timed out"
    if isinstance(error, EdenTimeoutError):
        return "Operation timed out"
    if isinstance(error, AgentError):
        return "Agent invocation failed"
    if isinstance(error, StructuredOutputError):
        return "Structured output extraction failed"
    if isinstance(error, CopyToWorktreeError):
        return "Worktree copy failed"
    if isinstance(error, SessionCaptureFailed):
        return "Session capture failed"
    if isinstance(error, HookError):
        return "Hook failed"
    if isinstance(error, EnvMergeError):
        return "Environment merge failed"
    if isinstance(error, CwdError):
        return "Invalid working directory"
    if isinstance(error, PromptError):
        return "Prompt resolution failed"
    if isinstance(error, ConfigError):
        return "Configuration error"
    if isinstance(error, Aborted):
        return "Aborted"

    # Sandbox / worktree (delayed import).
    try:
        from eden.sandboxes.errors import SandboxError
        from eden.worktree.errors import WorktreeError
    except ImportError:  # pragma: no cover — in-tree
        return "Error"
    if isinstance(error, SandboxError):
        return "Sandbox operation failed"
    if isinstance(error, WorktreeError):
        return "Git worktree operation failed"

    return "Error"


def format_error_message(error: EdenError) -> str:
    """Return a single-paragraph, user-friendly string for any ``EdenError``.

    The format is:

        <kind-prefix>: <message>
            [code: <code>]
            hint: <hint>

    Empty lines are omitted. ``code`` is always present; ``hint`` only
    appears when the error carries one or the formatter can synthesise
    one (e.g. for ``ProviderUnavailable`` we add "Is Docker running?").
    """
    if not isinstance(error, EdenError):
        raise TypeError(f"format_error_message expects an EdenError, got {type(error).__name__}")

    prefix = _kind_prefix(error)
    message = _message_of(error)
    code = _code_of(error)
    hint = _hint_of(error) or provider_hint(error) or worktree_hint(error)

    lines = [f"{prefix}: {message}"]
    lines.append(f"  code: {code}")
    if hint:
        lines.append(f"  hint: {hint}")

    return "\n".join(lines)


__all__ = ["format_error_message"]
