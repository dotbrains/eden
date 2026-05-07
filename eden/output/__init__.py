"""Structured output: declare and extract typed payloads from agent stdout."""

from __future__ import annotations

from eden.output._extract import extract_structured_output
from eden.output._types import Output, OutputDefinition

__all__ = ["Output", "OutputDefinition", "extract_structured_output"]
