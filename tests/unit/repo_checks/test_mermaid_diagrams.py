"""Structural lint for mermaid diagrams in markdown.

Catches the common failure modes — wrong fence, typo'd diagram keyword,
mismatched brackets — without requiring a JavaScript renderer. Will not
catch every semantic mermaid error, but ensures every diagram at least
parses past its preamble.
"""

from __future__ import annotations

import pytest

from tests.unit.repo_checks._mermaid import (
    iter_mermaid_blocks,
    markdown_files,
    validate_mermaid_block,
)
from tests.unit.repo_checks._paths import repo_root

pytestmark = pytest.mark.unit


def test_all_mermaid_diagrams_parse_structurally() -> None:
    root = repo_root()
    failures: list[str] = []
    block_count = 0
    for md in markdown_files(root):
        if not md.exists():
            continue
        for block in iter_mermaid_blocks(md):
            block_count += 1
            for err in validate_mermaid_block(block):
                failures.append(f"{block.file.relative_to(root)}:{block.start_line}: {err}")

    assert block_count > 0, "no mermaid blocks discovered — fix the discovery logic"
    assert failures == [], "mermaid diagram lint failures:\n" + "\n".join(failures)
