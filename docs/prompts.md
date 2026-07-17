# Prompts

Eden's `run()` accepts a prompt as either an inline string (`prompt=`) or a file path (`prompt_file=`); the chosen source is re-rendered before every iteration.

---

## Sources

Exactly one of `prompt=` or `prompt_file=` is required — supplying both, or neither, raises [`InvalidOptions`](python-api.md#errors). Read source: `eden/prompt/_source.py`.

### Literal string

```python
run(..., prompt="Refactor the cache module to use LRU eviction.")
```

The string is passed as-is to the agent. Best for one-shot tasks with no dynamic content.

Inline `prompt=` does **not** support `prompt_args` substitution — pairing them raises `InvalidOptions`. Use `prompt_file=` whenever you need substitution.

### File source

```python
from pathlib import Path

run(..., prompt_file=Path(".eden/prompt.md"))
```

The file is read as UTF-8 each iteration, so editing it between iterations updates the prompt the next time it's rendered. A missing file raises [`PromptError`](python-api.md#errors) with `code="prompt.file_missing"`; an unreadable file raises `code="prompt.file_unreadable"`.

`prompt_file` accepts either a `str` or `pathlib.Path`.

## `{{KEY}}` substitution

Eden substitutes `{{KEY}}` placeholders inside the prompt body. Substitution runs before shell-block expansion. Keys must match `[A-Za-z_][A-Za-z0-9_]*`; whitespace inside the braces is accepted, so `{{KEY}}` and `{{ KEY }}` are equivalent. Read source: `eden/prompt/_render.py`.

```python
run(
    ...,
    prompt_file=Path(".eden/prompt.md"),
    prompt_args={"MODULE": "auth", "TARGET": "src/auth.py"},
)
```

```markdown
# .eden/prompt.md
Add tests for {{MODULE}} in {{TARGET}}.
```

Unknown placeholders raise `PromptError` with `code="prompt.unknown_key"` — the hint lists the keys that _are_ defined. Extra `prompt_args` keys that are not referenced by the prompt emit a warning.

Each `prompt_args` value must be a string. A `None` value raises `PromptError`
with `code="prompt.missing_arg"` during non-interactive rendering; interactive
argument collection treats it as missing and asks for a replacement value.

### Built-in keys

Two keys are auto-injected on every render and **cannot** be supplied via `prompt_args` (doing so raises `InvalidOptions`):

- `{{SOURCE_BRANCH}}` — the worktree's branch (the one Eden is committing onto).
- `{{TARGET_BRANCH}}` — the branch Eden is configured to merge back onto, resolved from the host repo's HEAD at run start.

```markdown
You are working on `{{SOURCE_BRANCH}}`. Open a PR against `{{TARGET_BRANCH}}` when complete.
```

Built-ins win over user args if a name collides — but the collision is rejected up front.

## Shell blocks (`` !`cmd` ``)

Eden expands `` !`cmd` `` blocks **after** placeholder substitution by running each command via the sandbox handle's `exec()`. Multiple blocks in one prompt run concurrently, then their stdout (with one trailing newline stripped) is spliced back into the prompt in source order. Read source: `eden/prompt/_shell.py`.

```markdown
Current branch state:
!`git log --oneline -5`

Failing tests:
!`pytest -q 2>&1 | tail -20`
```

A non-zero exit raises `PromptError` with `code="prompt.shell_block_failed"`; the command's stderr (if any) becomes the error hint.

Because shell blocks execute through the sandbox handle, they observe the sandbox's filesystem and environment — not the host's. For bind-mount providers (`no_sandbox`, `docker`, `podman`) the two are effectively the same; for `isolated`/`daytona`/`vercel` the block runs against the synced sandbox state.

## Composition

The pipeline is:

1. Resolve source (`prompt=` or `prompt_file=`).
2. Substitute `{{KEY}}` placeholders (user args + built-ins).
3. Expand `` !`cmd` `` shell blocks via the sandbox handle.

So a `prompt_file` whose body mixes `{{MODULE}}` placeholders, `{{SOURCE_BRANCH}}` references, and `` !`git diff main` `` blocks is fully supported — the placeholders resolve first, then the shell command runs against the post-substitution text.

## See also

- [Python API: `run(...)`](python-api.md#run) — full signature, including `prompt`, `prompt_file`, `prompt_args`.
- [Errors](python-api.md#errors) — `PromptError` and `InvalidOptions` are how prompt failures surface.
- [How it works](how-it-works.md) — where prompt rendering sits in the iteration loop.
