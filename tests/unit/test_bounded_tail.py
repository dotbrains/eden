"""Verify BoundedTail caps memory while preserving the tail."""

from __future__ import annotations

import pytest

from eden.orchestrator._bounded_tail import DEFAULT_MAX_CHARS, BoundedTail

pytestmark = pytest.mark.unit


def test_empty_tail_is_empty_string() -> None:
    tail = BoundedTail()
    assert tail.to_string() == ""
    assert len(tail) == 0


def test_push_preserves_short_input_verbatim() -> None:
    tail = BoundedTail(max_chars=100)
    tail.push("hello")
    tail.push(" ")
    tail.push("world")
    assert tail.to_string() == "hello world"
    assert len(tail) == len("hello world")


def test_push_empty_string_is_noop() -> None:
    tail = BoundedTail()
    tail.push("anchor")
    tail.push("")
    assert tail.to_string() == "anchor"


def test_oldest_items_evicted_when_total_exceeds_budget() -> None:
    """Once over budget, the head drops; the tail survives."""
    tail = BoundedTail(max_chars=10)
    tail.push("aaaa")  # 4
    tail.push("bbbb")  # 8
    tail.push("cccc")  # 12 > 10 → evict 'aaaa'
    assert tail.to_string() == "bbbbcccc"
    assert len(tail) == 8


def test_single_oversize_item_is_truncated_to_its_own_tail() -> None:
    """A blob larger than ``max_chars`` is sliced to ``max_chars`` BEFORE landing."""
    tail = BoundedTail(max_chars=5)
    tail.push("0123456789")  # 10 chars → kept as "56789"
    assert tail.to_string() == "56789"
    assert len(tail) == 5


def test_to_string_never_exceeds_max_chars() -> None:
    """Repeated pushes never grow the joined output past the budget."""
    tail = BoundedTail(max_chars=20)
    for i in range(100):
        tail.push(f"line-{i}\n")
    assert len(tail.to_string()) <= 20


def test_separator_inserted_between_items() -> None:
    tail = BoundedTail(max_chars=100, separator="|")
    tail.push("a")
    tail.push("b")
    tail.push("c")
    assert tail.to_string() == "a|b|c"


def test_separator_cost_counted_in_eviction() -> None:
    """Eviction budget accounts for separator length, not just items."""
    # 3 items * 2 chars = 6, plus 2 separators * 2 chars = 10
    tail = BoundedTail(max_chars=10, separator=", ")
    tail.push("aa")
    tail.push("bb")
    tail.push("cc")
    assert tail.to_string() == "aa, bb, cc"
    # Adding a fourth item must evict 'aa'.
    tail.push("dd")
    assert tail.to_string() == "bb, cc, dd"


def test_default_max_is_64kib() -> None:
    """Sanity-check the constant doesn't regress under us."""
    assert DEFAULT_MAX_CHARS == 64 * 1024


def test_zero_max_chars_rejected() -> None:
    with pytest.raises(ValueError):
        BoundedTail(max_chars=0)


def test_tail_after_eviction_still_contains_recent_completion_signal() -> None:
    """The completion-signal contract: bounding never loses a tail-emitted tag.

    Eden's structured-output extractor scans the joined buffer for a
    closing ``<tag>...</tag>`` block the agent emits at the end. Verify
    that even after evicting many head lines, a final tag at the tail
    is still present.
    """
    tail = BoundedTail(max_chars=200)
    for i in range(500):
        tail.push(f"junk line {i}\n")
    tail.push("<result>{}</result>\n")
    assert "<result>{}</result>" in tail.to_string()
