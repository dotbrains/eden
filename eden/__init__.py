"""Eden — Python orchestrator for AI coding agents in sandboxed worktrees."""

from __future__ import annotations

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage
from eden._version import __version__
from eden.abort import AbortController, Aborted, AbortSignal
from eden.agents import (
    Agent,
    IterationContext,
    claude_code,
    cli_agent,
    codex,
    opencode,
    pi,
    simulated_agent,
)
from eden.errors import (
    ConfigError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
    SessionCaptureFailed,
    StepTimeout,
    StructuredOutputError,
)
from eden.lifecycle import Hook, HookPhase, Hooks, HostHooks, SandboxHooks
from eden.logging import Logging
from eden.orchestrator import create_worktree, run
from eden.output import Output, OutputDefinition
from eden.providers._protocols import IsolatedSandboxHandle
from eden.providers._types import BranchStrategy, FinalizeResult, Mount
from eden.streaming import StreamEvent

__all__ = [
    # cancellation
    "AbortController",
    "AbortSignal",
    "Aborted",
    # agent
    "Agent",
    # provider re-exports
    "BranchStrategy",
    "Commit",
    "ConfigError",
    "CwdError",
    # errors
    "EdenError",
    "EdenTimeoutError",
    "EnvMergeError",
    "FinalizeResult",
    # lifecycle
    "Hook",
    "HookError",
    "HookFailed",
    "HookPhase",
    "HookTimeout",
    "Hooks",
    "HostHooks",
    "IdleTimeout",
    "InvalidOptions",
    "IsolatedSandboxHandle",
    "Iteration",
    "IterationContext",
    # config / data
    "Logging",
    "Mount",
    "Output",
    "OutputDefinition",
    "PromptError",
    "RestAuthError",
    "RestError",
    "RestNotFoundError",
    "RestRateLimited",
    "RunResult",
    "SandboxHooks",
    "SessionCaptureFailed",
    "StepTimeout",
    "StreamEvent",
    "StructuredOutputError",
    "Timeouts",
    "Usage",
    "__version__",
    "claude_code",
    "cli_agent",
    "codex",
    "create_worktree",
    "opencode",
    # entrypoints
    "pi",
    "run",
    "simulated_agent",
]
