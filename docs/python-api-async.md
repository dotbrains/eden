# Python API: Async

`eden.aio` mirrors the three top-level entry points (`run`, `create_sandbox`,
`interactive`) as `async def` functions. Each is a thin `asyncio.to_thread`
wrapper around its sync counterpart: same arguments, same return type, and no
async-native primitives in the core. See
[ADR 0011](adr/0011-async-api-surface.md).

```python
import asyncio

import eden
from eden import aio
from eden.sandboxes.no_sandbox import provider as no_sandbox


async def main() -> None:
    # Single run.
    result = await aio.run(
        agent=eden.simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
    )

    # Concurrent runs.
    a, b = await asyncio.gather(
        aio.run(
            agent=...,
            sandbox=...,
            prompt="task A",
            branch_strategy=eden.BranchStrategy.named("eden/a"),
        ),
        aio.run(
            agent=...,
            sandbox=...,
            prompt="task B",
            branch_strategy=eden.BranchStrategy.named("eden/b"),
        ),
    )

    # create_sandbox.run() is sync; await it via asyncio.to_thread.
    s = await aio.create_sandbox(sandbox=no_sandbox())
    try:
        impl = await asyncio.to_thread(
            s.run,
            agent=...,
            prompt_file="implement.md",
            max_iterations=20,
        )
    finally:
        s.close()

asyncio.run(main())
```

Concurrency is bounded by asyncio's default `ThreadPoolExecutor`
(`min(32, cpu+4)` workers). Users running more concurrent tasks should size the
pool with `loop.set_default_executor(...)`. See
[ADR 0011](adr/0011-async-api-surface.md) for why eden does not async-ify the
core.
