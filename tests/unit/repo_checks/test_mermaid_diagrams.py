"""Structural lint for mermaid diagrams in markdown.

Catches the common failure modes — wrong fence, typo'd diagram keyword,
mismatched brackets — without requiring a JavaScript renderer. Will not
catch every semantic mermaid error, but ensures every diagram at least
parses past its preamble.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.unit.repo_checks._paths import repo_root

pytestmark = pytest.mark.unit


_SEQUENCE_RESERVED_KEYWORDS = frozenset(
    {
        "box",
        "loop",
        "alt",
        "opt",
        "par",
        "and",
        "critical",
        "break",
        "rect",
        "note",
        "participant",
        "actor",
        "activate",
        "deactivate",
        "autonumber",
        "link",
        "links",
        "properties",
        "details",
        "over",
        "right",
        "left",
        "of",
        "as",
        "else",
        "end",
    }
)


_KNOWN_DIAGRAM_TYPES = frozenset(
    {
        "flowchart",
        "graph",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "stateDiagram-v2",
        "erDiagram",
        "gantt",
        "pie",
        "gitGraph",
        "journey",
        "requirementDiagram",
        "mindmap",
        "timeline",
        "C4Context",
        "C4Container",
        "C4Component",
        "C4Dynamic",
        "C4Deployment",
        "quadrantChart",
        "xychart-beta",
        "block-beta",
        "packet-beta",
        "kanban",
        "architecture-beta",
        "sankey-beta",
    }
)


@dataclass(frozen=True)
class _Block:
    file: Path
    start_line: int
    body: str


def _iter_blocks(md: Path) -> Iterator[_Block]:
    fence_re = re.compile(r"^```(\w*)\s*$")
    in_fence: str | None = None
    buf: list[str] = []
    start = 0
    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
        m = fence_re.match(line)
        if m and in_fence is None:
            in_fence = m.group(1)
            buf = []
            start = i
            continue
        if m and in_fence is not None:
            if in_fence == "mermaid":
                yield _Block(file=md, start_line=start, body="\n".join(buf))
            in_fence = None
            buf = []
            continue
        if in_fence is not None:
            buf.append(line)


def _validate(block: _Block) -> list[str]:
    errors: list[str] = []
    body = block.body

    non_empty = [
        line for line in body.splitlines() if line.strip() and not line.strip().startswith("%%")
    ]
    if not non_empty:
        return ["empty mermaid block"]

    first_token = non_empty[0].split()[0]
    base = first_token.split(":", 1)[0]
    if base not in _KNOWN_DIAGRAM_TYPES:
        errors.append(
            f"unknown diagram type: {first_token!r} "
            "(first token must be one of mermaid's diagram keywords)"
        )

    for opener, closer in (("{", "}"), ("[", "]"), ("(", ")")):
        diff = body.count(opener) - body.count(closer)
        if diff != 0:
            errors.append(f"unbalanced {opener}{closer}: {diff:+d}")

    if base == "sequenceDiagram":
        errors.extend(_check_sequence_keywords(non_empty))

    return errors


_PARTICIPANT_RE = re.compile(r"^\s*(?:participant|actor)\s+(\S+)(?:\s+as\s+.*)?$")
_ARROW_RE = re.compile(r"^\s*(\S+?)\s*(?:-->>|->>|--x|-x|--\)|-\)|<<--|<<-|-->|->)\s*(\S+?)\s*:")


def _check_sequence_keywords(non_empty: list[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for line in non_empty:
        m = _PARTICIPANT_RE.match(line)
        if m:
            seen.add(m.group(1))
            continue
        a = _ARROW_RE.match(line)
        if a:
            seen.update({a.group(1), a.group(2)})
    for name in seen:
        if name.lower() in _SEQUENCE_RESERVED_KEYWORDS:
            errors.append(
                f"participant identifier {name!r} collides with mermaid reserved "
                "keyword (case-insensitive); rename to avoid parser ambiguity"
            )
    return errors


def _markdown_files(repo_root: Path) -> Iterable[Path]:
    yield repo_root / "README.md"
    for md in sorted((repo_root / "docs").rglob("*.md")):
        if "superpowers" in md.parts:
            continue
        yield md


def test_all_mermaid_diagrams_parse_structurally() -> None:
    root = repo_root()
    failures: list[str] = []
    block_count = 0
    for md in _markdown_files(root):
        if not md.exists():
            continue
        for block in _iter_blocks(md):
            block_count += 1
            for err in _validate(block):
                failures.append(f"{block.file.relative_to(root)}:{block.start_line}: {err}")

    assert block_count > 0, "no mermaid blocks discovered — fix the discovery logic"
    assert failures == [], "mermaid diagram lint failures:\n" + "\n".join(failures)
