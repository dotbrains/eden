"""Public surface for sandbox providers and the create_sandbox factory."""

from __future__ import annotations

from eden.sandboxes._factory import Sandbox, create_sandbox

__all__ = ["Sandbox", "create_sandbox"]
