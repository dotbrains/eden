"""E2E: structured output extraction end-to-end via simulated_agent."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_output_string_extracted_to_result(e2e_git_repo: Path) -> None:
    result = eden.run(
        agent=eden.simulated_agent(
            output="thinking...\n<answer>42</answer>\n<promise>COMPLETE</promise>\n",
        ),
        sandbox=no_sandbox(),
        prompt="emit your answer inside <answer>...</answer>",
        max_iterations=1,
        output=eden.Output.string(tag="answer"),
    )
    assert result.output == "42"


def test_output_object_extracted_and_validated(e2e_git_repo: Path) -> None:
    def schema(raw: object) -> dict[str, int]:
        assert isinstance(raw, dict)
        return {"count": int(raw["count"])}

    payload = '{"count": 7}'
    result = eden.run(
        agent=eden.simulated_agent(
            output=f"<result>{payload}</result>\n<promise>COMPLETE</promise>\n",
        ),
        sandbox=no_sandbox(),
        prompt="put JSON inside <result>...</result>",
        max_iterations=1,
        output=eden.Output.object(tag="result", schema=schema),
    )
    assert result.output == {"count": 7}


def test_output_missing_tag_raises_structured_output_error(e2e_git_repo: Path) -> None:
    with pytest.raises(eden.StructuredOutputError) as ex:
        eden.run(
            agent=eden.simulated_agent(output="no tag\n<promise>COMPLETE</promise>\n"),
            sandbox=no_sandbox(),
            prompt="emit <answer>...</answer>",
            max_iterations=1,
            output=eden.Output.string(tag="answer"),
        )
    assert ex.value.tag == "answer"
    assert ex.value.branch  # populated
    assert ex.value.raw_matched is None
    # The error carries the iteration's session
    # id and captured JSONL path. simulated_agent doesn't emit either,
    # so both come through as None; the orchestrator's plumbing is
    # exercised regardless.
    assert ex.value.session_id is None
    assert ex.value.session_file_path is None


def test_output_max_iterations_gt_1_rejected(e2e_git_repo: Path) -> None:
    with pytest.raises(eden.InvalidOptions) as ex:
        eden.run(
            agent=eden.simulated_agent(output="x\n"),
            sandbox=no_sandbox(),
            prompt="emit <a>...</a>",
            max_iterations=2,
            output=eden.Output.string(tag="a"),
        )
    assert "max_iterations" in ex.value.message


def test_output_tag_not_in_prompt_rejected(e2e_git_repo: Path) -> None:
    with pytest.raises(eden.InvalidOptions) as ex:
        eden.run(
            agent=eden.simulated_agent(output="x\n"),
            sandbox=no_sandbox(),
            prompt="prompt without the tag",
            max_iterations=1,
            output=eden.Output.string(tag="answer"),
        )
    assert "<answer>" in ex.value.message


def test_no_output_keeps_field_none(e2e_git_repo: Path) -> None:
    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
    )
    assert result.output is None
