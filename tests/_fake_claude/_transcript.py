"""Builder for stream-json transcripts used by the fake claude shim."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Transcript:
    _lines: list[dict[str, object]] = field(default_factory=list)

    def system_init(self) -> Transcript:
        self._lines.append({"type": "system", "subtype": "init"})
        return self

    def text(self, text: str) -> Transcript:
        self._lines.append(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": text}]},
            }
        )
        return self

    def tool(self, name: str, tool_input: dict[str, object]) -> Transcript:
        self._lines.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": name, "input": tool_input},
                    ],
                },
            }
        )
        return self

    def result(
        self,
        *,
        session_id: str,
        input_tokens: int = 10,
        output_tokens: int = 20,
    ) -> Transcript:
        self._lines.append(
            {
                "type": "result",
                "session_id": session_id,
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": output_tokens,
                },
            }
        )
        return self

    def stream_json_lines(self) -> list[str]:
        return [json.dumps(line) for line in self._lines]

    def session_jsonl_body(self, *, sandbox_cwd: str) -> str:
        """The contents Claude Code writes to ~/.claude/projects/<slug>/<id>.jsonl.

        For the shim, we mirror only the bits Eden's rewriter cares about: a
        cwd line plus a tool_input line containing a sandbox-prefixed path.
        """
        body: list[dict[str, object]] = [
            {"cwd": sandbox_cwd},
            {"tool_input": {"file_path": f"{sandbox_cwd}/src/x.py"}},
        ]
        return "\n".join(json.dumps(b) for b in body) + "\n"
