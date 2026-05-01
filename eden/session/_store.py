"""Read a Claude Code session JSONL and write a path-rewritten copy."""

from __future__ import annotations

from pathlib import Path

from eden.session._encode import rewrite_paths


def write_session_copy(
    *,
    src: Path,
    dest: Path,
    sandbox_prefix: str,
    host_prefix: str,
) -> None:
    """Read ``src`` line by line, run ``rewrite_paths`` on each line, write to ``dest``.

    ``dest``'s parent directory is created if missing. Empty lines are
    preserved verbatim. Lines that don't parse as JSON pass through unchanged.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as fp_in, dest.open("w", encoding="utf-8") as fp_out:
        for raw in fp_in:
            line = raw.rstrip("\n")
            if not line:
                fp_out.write(raw)
                continue
            rewritten = rewrite_paths(
                line,
                sandbox_prefix=sandbox_prefix,
                host_prefix=host_prefix,
            )
            fp_out.write(rewritten + "\n")
