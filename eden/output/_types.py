"""Output definition dataclasses + the public ``Output`` namespace.

``Output.object(tag=..., schema=...)`` declares a JSON-typed payload extracted
from ``<tag>...</tag>`` in agent stdout, validated by calling ``schema(parsed)``.
``schema`` is any ``Callable[[object], T]`` that returns a validated value or
raises on failure — works with pydantic ``Model.model_validate``, dataclass
factories, msgspec, or hand-rolled validators.

``Output.string(tag=...)`` extracts the whitespace-trimmed contents of
``<tag>...</tag>`` as a plain string — no JSON parsing.

The dataclasses are intentionally exposed under leading-underscore names so the
public surface is just ``Output``; consumers discriminate on ``isinstance``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class _OutputObject(Generic[T]):
    tag: str
    schema: Callable[[object], T]


@dataclass(frozen=True)
class _OutputString:
    tag: str


OutputDefinition: TypeAlias = "_OutputObject[object] | _OutputString"


class Output:
    """Helpers for declaring structured output on ``run()``."""

    @staticmethod
    def object(*, tag: str, schema: Callable[[object], T]) -> _OutputObject[T]:
        """Declare an object payload extracted from ``<tag>...</tag>``.

        ``schema`` is invoked with the JSON-parsed contents and must return a
        validated value or raise. Markdown code fences (`````json ... `````)
        around the JSON are stripped before parsing.
        """
        return _OutputObject(tag=tag, schema=schema)

    @staticmethod
    def string(*, tag: str) -> _OutputString:
        """Declare a string payload extracted from ``<tag>...</tag>``.

        The matched contents are returned with surrounding whitespace stripped.
        No JSON parsing, no validation.
        """
        return _OutputString(tag=tag)
