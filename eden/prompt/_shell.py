"""!`cmd` shell-block expansion via the sandbox handle."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from eden.errors import PromptError
from eden.providers._protocols import SandboxHandle

_BLOCK_RE = re.compile(r"!`(?P<cmd>[^`]+)`")


def expand_shell_blocks(text: str, *, handle: SandboxHandle) -> str:
    """Run each !`cmd` via handle.exec and substitute its stdout (one trailing \\n stripped).

    Blocks run concurrently and are spliced back into the prompt in source order.
    Non-zero exit → PromptError(code="prompt.shell_block_failed").
    """
    matches = list(_BLOCK_RE.finditer(text))
    if not matches:
        return text

    def _run(match: re.Match[str]) -> str:
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
        return body

    with ThreadPoolExecutor(max_workers=len(matches)) as pool:
        bodies = list(pool.map(_run, matches))

    pos = 0
    out: list[str] = []
    for match, body in zip(matches, bodies, strict=True):
        out.append(text[pos : match.start()])
        out.append(body)
        pos = match.end()
    out.append(text[pos:])
    return "".join(out)
