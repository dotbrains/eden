"""Verify ``Output.object(schema=...)`` validator resolution.

Tests use hand-rolled stub classes that mimic the pydantic v1 / v2 and
msgspec-style surfaces. No third-party deps required; mirrors what the
real classes look like at the duck-typing level Eden uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from eden.errors import StructuredOutputError
from eden.output import Output, extract_structured_output
from eden.output._validator import resolve_validator

pytestmark = pytest.mark.unit


# ---- resolve_validator unit tests -----------------------------------------


def test_plain_callable_returned_directly() -> None:
    def my_validator(d: object) -> str:
        return str(d)

    out = resolve_validator(my_validator)
    assert out is my_validator


def test_pydantic_v2_class_uses_model_validate() -> None:
    """Detect classmethod ``model_validate`` (the v2 surface)."""
    captured: dict[str, Any] = {}

    class FakePydanticV2:
        @classmethod
        def model_validate(cls, data: object) -> str:
            captured["data"] = data
            return "v2-ok"

    validator = resolve_validator(FakePydanticV2)
    result = validator({"x": 1})
    assert result == "v2-ok"
    assert captured["data"] == {"x": 1}


def test_pydantic_v1_class_uses_parse_obj() -> None:
    """Detect ``parse_obj`` + ``__fields__`` (the v1 surface)."""
    captured: dict[str, Any] = {}

    class FakePydanticV1:
        __fields__: ClassVar[dict[str, Any]] = {}

        @classmethod
        def parse_obj(cls, data: object) -> str:
            captured["data"] = data
            return "v1-ok"

    validator = resolve_validator(FakePydanticV1)
    result = validator({"x": 2})
    assert result == "v1-ok"
    assert captured["data"] == {"x": 2}


def test_parse_obj_without_fields_falls_through_to_callable() -> None:
    """A class with ``parse_obj`` but no ``__fields__`` is NOT pydantic v1.

    Falls back to calling the class as a callable.
    """

    class HasParseObjButNotV1:
        def __init__(self, data: object) -> None:
            self.data = data

        @classmethod
        def parse_obj(cls, data: object) -> str:
            raise AssertionError("should not be called — no __fields__")

    inst = resolve_validator(HasParseObjButNotV1)({"x": 3})
    assert isinstance(inst, HasParseObjButNotV1)
    assert inst.data == {"x": 3}


def test_dataclass_factory_works_via_callable_path() -> None:
    @dataclass
    class Item:
        x: int

    # User-provided factory: dataclass(**dict).
    validator = resolve_validator(lambda d: Item(**d))
    item = validator({"x": 7})
    assert isinstance(item, Item)
    assert item.x == 7


def test_non_callable_non_validator_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="requires a callable"):
        resolve_validator(42)


# ---- End-to-end extract_structured_output --------------------------------


def test_extract_with_pydantic_v2_style_class() -> None:
    """End-to-end: ``Output.object(schema=PydanticModel)`` extracts + validates."""

    class FakeUser:
        def __init__(self, name: str, age: int) -> None:
            self.name = name
            self.age = age

        @classmethod
        def model_validate(cls, data: object) -> FakeUser:
            assert isinstance(data, dict)
            return cls(name=data["name"], age=data["age"])

    stdout = '<user>{"name": "alice", "age": 30}</user>'
    result = extract_structured_output(
        stdout,
        Output.object(tag="user", schema=FakeUser),
        branch="HEAD",
    )
    assert isinstance(result, FakeUser)
    assert result.name == "alice"
    assert result.age == 30


def test_extract_validation_failure_raises_structured_output_error() -> None:
    """When the validator raises, the orchestrator surfaces a typed error."""

    class StrictPydanticV2:
        @classmethod
        def model_validate(cls, data: object) -> StrictPydanticV2:
            raise ValueError("validation: field 'foo' is required")

    stdout = '<r>{"x": 1}</r>'
    with pytest.raises(StructuredOutputError) as exc:
        extract_structured_output(
            stdout,
            Output.object(tag="r", schema=StrictPydanticV2),
            branch="HEAD",
        )
    assert exc.value.code == "output.validation_failed"
    assert isinstance(exc.value.cause, ValueError)


def test_extract_callable_schema_still_works() -> None:
    """Back-compat: the existing ``schema=callable`` path still works."""
    stdout = '<n>{"value": 42}</n>'
    result = extract_structured_output(
        stdout,
        Output.object(tag="n", schema=lambda d: int(d["value"])),  # type: ignore[index]
        branch="HEAD",
    )
    assert result == 42
