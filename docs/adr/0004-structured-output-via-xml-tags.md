# ADR 0004 — Structured output via XML tags + callable schema

**Status:** Accepted (2026-05-07).

## Context

Many agent workflows want a typed payload back, not a free-text response. A planner agent in `parallel-planner` needs to emit a list of tasks. A research agent might emit a citation list. A reviewer might emit a verdict.

Three options were considered:

1. **Tool-call interface** — define a virtual tool the agent must invoke; parse the tool call's arguments. Requires every agent provider to expose tool-use, which `cli_agent`, `pi`, `opencode`, and `codex` don't natively. Couples eden to the Anthropic Messages API shape.
2. **JSON-Schema validation with a baked-in dependency** — adopt pydantic or jsonschema as a runtime dep, ask users to declare a model, validate parsed JSON against it. Forces a dependency on every eden install for a feature that's optional. Locks the schema-validation library into eden's API surface.
3. **XML-tag + callable schema** — agent emits `<tag>JSON</tag>` somewhere in stdout. Eden extracts the **last** matching block, optionally strips a Markdown code fence, `json.loads` it, and calls a user-supplied `schema(parsed)` callable. The callable is the only validation layer — pydantic, attrs, msgspec, hand-rolled `assert isinstance(...)` all work.

## Decision

Adopt option 3. `Output.object(tag, schema)` and `Output.string(tag)` declare the contract. Failures raise `StructuredOutputError` carrying `tag`, `raw_matched`, `branch`, and `preserved_worktree_path`.

Two entry-time validations:

- `max_iterations == 1` is required. Loop iterations would discard the agent's intermediate matches, so eden's `output=` extraction would silently shadow the wrong block.
- The literal `<tag>` substring must appear in the prompt source. The agent has to be told what tag to emit; an `output=` arg with no matching prompt instruction is a configuration bug.

The extractor takes the **last** matching block. Agents often "think out loud" with provisional JSON before committing to a final answer; last-match is the right choice.

## Consequences

- Eden has zero schema-library dependencies; users plug in whatever they prefer. `schema=MyPydanticModel.model_validate` works. `schema=lambda raw: MyDataclass(**raw)` works. `schema=lambda raw: raw` (passthrough) works.
- The XML-tag approach works equally well for any agent that produces text — Claude Code, Codex, Pi, OpenCode, custom `cli_agent` wrappers.
- The callable schema gives users full control over downstream typing. `Output.object` itself is generic over `T`, so `result.output` is typed as the schema's return type for users who care.
- Code-fence unwrapping (` ```json ... ``` ` and bare ` ``` ... ``` `) is built in. Models often hedge by wrapping JSON in fences; ignoring the fence at parse time avoids brittle prompt engineering.
- `RunResult.output: object | None` lives outside the `iterations` list — extraction runs once after the loop completes, against the full concatenated stdout.

## See also

- [`docs/python-api.md` — Structured output](../python-api.md#structured-output)
- `eden/output/` — implementation
- This ADR adopts a Standard-Schema-style shape adapted to Python's looser type ecosystem.
