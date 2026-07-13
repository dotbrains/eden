"""Runtime errors for the eden package.

Concrete errors store ``cause`` without setting ``__cause__``. Callers who
want chained tracebacks must use ``raise XError(..., cause=e) from e``.
"""

from __future__ import annotations

from eden._config_errors import ConfigError as ConfigError
from eden._config_errors import CwdError as CwdError
from eden._config_errors import EnvMergeError as EnvMergeError
from eden._config_errors import FloxEnvError as FloxEnvError
from eden._config_errors import InvalidOptions as InvalidOptions
from eden._config_errors import PromptError as PromptError
from eden._error_base import EdenError as EdenError
from eden._hook_errors import HookError as HookError
from eden._hook_errors import HookFailed as HookFailed
from eden._hook_errors import HookTimeout as HookTimeout
from eden._rest_errors import RestAuthError as RestAuthError
from eden._rest_errors import RestError as RestError
from eden._rest_errors import RestNotFoundError as RestNotFoundError
from eden._rest_errors import RestRateLimited as RestRateLimited
from eden._runtime_errors import AgentError as AgentError
from eden._runtime_errors import CopyToWorktreeError as CopyToWorktreeError
from eden._runtime_errors import SessionCaptureFailed as SessionCaptureFailed
from eden._runtime_errors import SessionNotFound as SessionNotFound
from eden._runtime_errors import StructuredOutputError as StructuredOutputError
from eden._timeout_errors import Aborted as Aborted
from eden._timeout_errors import EdenTimeoutError as EdenTimeoutError
from eden._timeout_errors import IdleTimeout as IdleTimeout
from eden._timeout_errors import StepTimeout as StepTimeout
