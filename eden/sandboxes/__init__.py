"""Public surface for sandbox providers and the create_sandbox factory."""

from __future__ import annotations

from eden.sandboxes._factory import create_sandbox
from eden.sandboxes._sandbox import Sandbox

__all__ = ["Sandbox", "create_sandbox"]
