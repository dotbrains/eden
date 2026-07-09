"""Run-option helpers for reusable sandbox wrappers."""

from __future__ import annotations

from eden.errors import InvalidOptions


def validate_sandbox_run_options(
    *,
    resume_session: str | None,
    fork_session: bool,
    max_iterations: int,
    output_tag: str | None,
    prompt_text: str,
) -> None:
    if resume_session is not None and max_iterations != 1:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "resume_session= is only valid with max_iterations=1; "
                f"got max_iterations={max_iterations}"
            ),
        )
    if fork_session and resume_session is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="fork_session=True requires resume_session=<id>",
            hint=(
                "fork continues a captured session under a new id; "
                "pass resume_session=<id> alongside fork_session=True"
            ),
        )
    if output_tag is None:
        return
    if max_iterations != 1:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"output= is only valid with max_iterations=1; got max_iterations={max_iterations}"
            ),
        )
    tag_marker = f"<{output_tag}>"
    if tag_marker not in prompt_text:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"output tag {tag_marker} not referenced in prompt; "
                "the agent must be told which tag to emit"
            ),
        )


__all__ = ["validate_sandbox_run_options"]
