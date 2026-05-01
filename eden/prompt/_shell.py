"""!`cmd` shell-block expansion via the sandbox handle."""

from __future__ import annotations

import re

from eden.errors import PromptError
from eden.providers._protocols import SandboxHandle

_BLOCK_RE = re.compile(r"!`(?P<cmd>[^`]+)`")


def expand_shell_blocks(text: str, *, handle: SandboxHandle) -> str:
    """Run each !`cmd` via handle.exec and substitute its stdout (one trailing \\n stripped).

    Blocks run sequentially. Non-zero exit → PromptError(code="prompt.shell_block_failed").
    """
    pos = 0
    out: list[str] = []
    for match in _BLOCK_RE.finditer(text):
        out.append(text[pos : match.start()])
        cmd = match.group("cmd").strip()
        result = handle.exec(cmd)
        if result.exit_code != 0:
            raise PromptError(
                code="prompt.shell_block_failed",
                message=f"prompt shell block {cmd!r} exited {result.exit_code}",
                hint=result.stderr.strip() or None,
            )
        body = result.stdout
        if body.endswith("\n"):
            body = body[:-1]
        out.append(body)
        pos = match.end()
    out.append(text[pos:])
    return "".join(out)
