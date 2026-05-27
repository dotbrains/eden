"""Resolve ``Output.object(schema=...)`` against the Python validator ecosystem.

Eden's original contract was ``schema: Callable[[object], T]``, so any plain
callable (a lambda, a function, a bound method like ``Model.model_validate``)
worked. This module adds ergonomic detection so callers can pass *classes*
from the common validator libraries directly:

* **pydantic v2 ``BaseModel``** — has the ``model_validate`` classmethod;
  ``Output.object(schema=MyModel)`` invokes ``MyModel.model_validate(parsed)``
  instead of ``MyModel(parsed)`` (which would treat ``parsed`` as positional
  and fail since BaseModel takes kwargs).
* **pydantic v1 ``BaseModel``** — has ``parse_obj`` + ``__fields__``; ditto
  with ``MyModel.parse_obj(parsed)``.
* Anything else callable → invoked directly (existing behaviour); covers
  dataclass factories, attrs classes (with ``__init__``-accepting-dict
  wrappers), msgspec ``msgspec.convert``-style callables, and hand-rolled
  validators.

No new package dependencies — every detection is via ``getattr`` + ``callable``
duck-typing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")

# Public-ish alias so type hints elsewhere read clearly.
# ``Any`` is honest: a validator can be a callable, a class, or any object
# duck-typed to expose ``model_validate`` / ``parse_obj``.
Validator = Any


def resolve_validator(schema: Validator) -> Callable[[object], Any]:
    """Return a single-argument callable that validates a parsed JSON object.

    Detection (in order):

    1. ``model_validate`` classmethod → pydantic v2 style.
    2. ``parse_obj`` method + ``__fields__`` attribute → pydantic v1 style.
    3. plain callable → invoked directly.

    Raises ``TypeError`` only for objects that match none of the above.
    """
    # Pydantic v2 BaseModel class (and any future validator with the same shape).
    model_validate = getattr(schema, "model_validate", None)
    if callable(model_validate):
        result: Callable[[object], Any] = model_validate
        return result

    # Pydantic v1 BaseModel class. ``__fields__`` distinguishes a model class
    # from a random object that happens to have a ``parse_obj`` method.
    parse_obj = getattr(schema, "parse_obj", None)
    if callable(parse_obj) and hasattr(schema, "__fields__"):
        v1: Callable[[object], Any] = parse_obj
        return v1

    # Plain callable — the original Eden contract.
    if callable(schema):
        plain: Callable[[object], Any] = schema
        return plain

    raise TypeError(
        f"Output.object(schema=...) requires a callable or a validator class "
        f"with model_validate / parse_obj; got {type(schema).__name__}"
    )


__all__ = ["Validator", "resolve_validator"]
