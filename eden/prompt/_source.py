"""Prompt source resolution: xor validation + file read + reserved-key check."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from eden.errors import InvalidOptions, PromptError

_RESERVED_KEYS = frozenset({"SOURCE_BRANCH", "TARGET_BRANCH"})


def resolve_source(
    *,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: Mapping[str, str] | None,
) -> str:
    if prompt is None and prompt_file is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="must supply exactly one of prompt or prompt_file",
            hint="pass prompt=... for inline text or prompt_file=... for a file path",
        )
    if prompt is not None and prompt_file is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="prompt and prompt_file are mutually exclusive",
            hint="pass exactly one",
        )
    if prompt is not None and prompt_args:
        raise InvalidOptions(
            code="config.invalid_options",
            message="prompt_args requires prompt_file (no substitution on inline text)",
            hint="move the prompt to a file or drop prompt_args",
        )
    if prompt_args:
        bad = sorted(set(prompt_args) & _RESERVED_KEYS)
        if bad:
            raise InvalidOptions(
                code="config.invalid_options",
                message=f"prompt_args may not set reserved keys: {bad}",
                hint="reserved keys are auto-injected: SOURCE_BRANCH, TARGET_BRANCH",
            )

    if prompt is not None:
        return prompt

    assert prompt_file is not None
    path = Path(prompt_file)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(
            code="prompt.file_missing",
            message=f"prompt_file not found: {path}",
            hint="check the path",
            cause=exc,
        ) from exc
    except OSError as exc:
        raise PromptError(
            code="prompt.file_unreadable",
            message=f"could not read prompt_file {path}: {exc}",
            cause=exc,
        ) from exc
