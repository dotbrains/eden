"""Verify env layer merge with collision detection."""

from __future__ import annotations

import pytest

from eden.env import merge_env
from eden.errors import EnvMergeError

pytestmark = pytest.mark.unit


def test_disjoint_keys_union() -> None:
    out = merge_env({"A": "1"}, {"B": "2"})
    assert out == {"A": "1", "B": "2"}


def test_same_key_same_value_idempotent() -> None:
    out = merge_env({"A": "1"}, {"A": "1"})
    assert out == {"A": "1"}


def test_same_key_different_value_raises() -> None:
    with pytest.raises(EnvMergeError) as excinfo:
        merge_env({"A": "1"}, {"A": "2"})
    assert excinfo.value.code == "config.env_merge"
    assert "A" in excinfo.value.message


def test_three_layers_disjoint() -> None:
    out = merge_env({"A": "1"}, {"B": "2"}, {"C": "3"})
    assert out == {"A": "1", "B": "2", "C": "3"}


def test_three_layers_collision_lists_layer_index() -> None:
    with pytest.raises(EnvMergeError) as excinfo:
        merge_env({"A": "1"}, {}, {"A": "9"})
    assert "A" in excinfo.value.message


def test_empty_layers() -> None:
    assert merge_env() == {}
    assert merge_env({}) == {}
    assert merge_env({}, {}) == {}


def test_no_layer_mutation() -> None:
    a = {"X": "1"}
    b = {"Y": "2"}
    merge_env(a, b)
    assert a == {"X": "1"}
    assert b == {"Y": "2"}
