"""Centralized formatter for surface-friendly error messages.

Eden's error taxonomy spans three sub-packages:

* ``eden.errors`` — top-level ``EdenError`` subclasses (config, agent, REST,
  hooks, timeouts, structured output, session capture).
* ``eden.sandboxes.errors`` — ``SandboxError`` family (provider-unavailable,
  image-not-found, exec failures, mount config).
* ``eden.worktree.errors`` — git worktree problems.

Every concrete error already attaches a structured ``code`` and a
human-readable ``message``; many already carry a ``hint``. Upstream's
``ErrorHandler.formatErrorMessage`` (``src/ErrorHandler.ts``) shows the
value of *one* place that consults all of them and returns a single
display string with a friendlier prefix.

This module ports that. CLI surfaces (``eden run``, REPL drivers,
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


def _provider_hint(error: EdenError) -> str | None:
    """Synthesise a recovery hint for SandboxError types that don't carry one.

    Imported lazily to keep this module standalone (no circular dep on
    ``eden.sandboxes`` for callers that only need ``format_error_message``).
    """
    try:
        from eden.sandboxes.errors import (
            ContainerStartFailed,
            ExecFailed,
            ExecTimeout,
            ImageNotFound,
            ImageUidMismatch,
            MountConfigError,
            ProviderUnavailable,
            UnsupportedStrategy,
        )
    except ImportError:  # pragma: no cover — sandboxes is in-tree
        return None

    if isinstance(error, ProviderUnavailable):
        # ``provider`` and ``binary`` are set on the instance.
        binary = getattr(error, "binary", "the runtime")
        provider = getattr(error, "provider", "")
        if provider == "docker":
            return "Is Docker running? Install Docker Desktop or `brew install --cask docker`."
        if provider == "podman":
            return (
                "Is Podman installed and running? `brew install podman` "
                "then `podman machine start`."
            )
        return f"Install {binary!r} and ensure it is on PATH, then re-run."
    if isinstance(error, ImageNotFound):
        image = getattr(error, "image", "<image>")
        return (
            f"Build the image first: `docker build -t {image} -f .eden/Dockerfile .`. "
            f"Or pull it: `docker pull {image}`."
        )
    if isinstance(error, ContainerStartFailed):
        return (
            "The container exited immediately. Check the image's ENTRYPOINT / "
            "CMD and confirm Docker daemon is healthy (`docker ps`)."
        )
    if isinstance(error, ImageUidMismatch):
        return (
            "Rebuild the image with `--build-arg AGENT_UID=<host-uid> "
            "AGENT_GID=<host-gid>` or pass matching `container_uid=`/`container_gid=`."
        )
    if isinstance(error, MountConfigError):
        return (
            "Move the mount target inside the sandbox HOME, or pre-create the "
            "parent directory in your image."
        )
    if isinstance(error, ExecTimeout):
        timeout = getattr(error, "timeout", None)
        if timeout:
            return (
                f"Increase `Timeouts.iteration_step` or the per-call "
                f"timeout (currently {timeout}s)."
            )
        return "Increase the per-call timeout or `Timeouts.iteration_step`."
    if isinstance(error, ExecFailed):
        return "Inspect the captured stderr; rerun with `Logging.file(...)` to persist it."
    if isinstance(error, UnsupportedStrategy):
        return "Pick a strategy this provider supports, or switch to docker/no_sandbox."
    return None


def _worktree_hint(error: EdenError) -> str | None:
    try:
        from eden.worktree.errors import (
            BranchExists,
            DirtyHostBlocked,
            GitCommandFailed,
            WorktreeLocked,
        )
    except ImportError:  # pragma: no cover — worktree is in-tree
        return None

    if isinstance(error, WorktreeLocked):
        pid = getattr(error, "holder_pid", None)
        return (
            f"Another eden process (pid {pid}) is using this worktree. "
            "Wait for it, or delete the stale lockfile."
        )
    if isinstance(error, DirtyHostBlocked):
        return "Commit or stash the listed files, or pass `allow_dirty=True`."
    if isinstance(error, BranchExists):
        return (
            "Pass `branch_strategy=BranchStrategy.named(<unique-name>)` "
            "or delete the existing branch."
        )
    if isinstance(error, GitCommandFailed):
        return "Inspect the failing git command; ensure the repo is healthy (`git fsck`)."
    return None


def _kind_prefix(error: EdenError) -> str:
    """Return a short, upstream-style noun phrase for the error class.

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
    hint = _hint_of(error) or _provider_hint(error) or _worktree_hint(error)

    lines = [f"{prefix}: {message}"]
    lines.append(f"  code: {code}")
    if hint:
        lines.append(f"  hint: {hint}")

    return "\n".join(lines)


__all__ = ["format_error_message"]
