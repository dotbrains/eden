"""Output definition dataclasses + the public ``Output`` namespace.

``Output.object(tag=..., schema=...)`` declares a JSON-typed payload extracted
from ``<tag>...</tag>`` in agent stdout, validated against ``schema``.

Eden detects three validator shapes at extraction time (see
:mod:`eden.output._validator` for the resolution order):

- a **pydantic v2 ``BaseModel`` class** (has ``model_validate``);
- a **pydantic v1 ``BaseModel`` class** (has ``parse_obj`` + ``__fields__``);
- any **plain callable** of shape ``(parsed: object) -> T`` — covers
  dataclass factories, attrs/msgspec wrappers, ``Model.model_validate``
  bound methods, and hand-rolled validators.

``Output.string(tag=...)`` extracts the whitespace-trimmed contents of
``<tag>...</tag>`` as a plain string — no JSON parsing.

The dataclasses are intentionally exposed under leading-underscore names so the
public surface is just ``Output``; consumers discriminate on ``isinstance``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar

T = TypeVar("T")

# Union of every shape ``Output.object(schema=...)`` accepts. ``Any`` is the
# honest type — pydantic ``BaseModel`` subclasses are classes, dataclass
# factories are functions, ``Model.model_validate`` is a bound classmethod,
# all of which would otherwise need their own protocols.
Validator = Callable[[object], T] | type[Any]


@dataclass(frozen=True)
class _OutputObject(Generic[T]):
    tag: str
    schema: Validator[T]
    max_retries: int = 0


@dataclass(frozen=True)
class _OutputString:
    tag: str
    max_retries: int = 0


OutputDefinition: TypeAlias = "_OutputObject[object] | _OutputString"


class Output:
    """Helpers for declaring structured output on ``run()``."""

    @staticmethod
    def object(*, tag: str, schema: Validator[T], max_retries: int = 0) -> _OutputObject[T]:
        """Declare an object payload extracted from ``<tag>...</tag>``.

        ``schema`` can be:

        * a **pydantic ``BaseModel`` class** (v1 or v2) — Eden invokes
          ``model_validate(parsed)`` / ``parse_obj(parsed)`` directly, so
          ``schema=MyModel`` works without writing
          ``schema=MyModel.model_validate``;
        * a **dataclass class** wrapped as ``schema=lambda d: MyDataclass(**d)``;
        * an **attrs class** wrapped similarly;
        * a **msgspec converter** like ``schema=lambda d: msgspec.convert(d, MyType)``;
        * any **callable** of shape ``(parsed: object) -> T``.

        Markdown code fences (```` ```json ... ``` ````) around the JSON are
        stripped before parsing.

        ``max_retries`` (default ``0``) auto-retries the run when extraction or
        validation fails: ``run()`` resumes the failing session with corrective
        feedback (or, for agents without session capture, re-runs the prompt)
        up to ``max_retries`` extra times before raising ``StructuredOutputError``.
        """
        return _OutputObject(tag=tag, schema=schema, max_retries=max_retries)

    @staticmethod
    def string(*, tag: str, max_retries: int = 0) -> _OutputString:
        """Declare a string payload extracted from ``<tag>...</tag>``.

        The matched contents are returned with surrounding whitespace stripped.
        No JSON parsing, no validation.

        ``max_retries`` (default ``0``) auto-retries when the tag is missing —
        see :meth:`object`.
        """
        return _OutputString(tag=tag, max_retries=max_retries)
