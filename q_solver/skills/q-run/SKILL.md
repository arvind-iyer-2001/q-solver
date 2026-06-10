---
name: q-run
description: Run arbitrary q/kdb+ code immediately in the q-solver container and return raw output
---

# q-run

Run q/kdb+ code immediately. No solve loop, no test cases. Raw output only.

## Steps

1. Call `run_q` with the user's code exactly as provided.
2. If `run_q` raises an error mentioning "q-solver install", tell the user:
   > "Q Solver is not set up yet. Run `q-solver install` in your terminal to get started.
   > Get your KX license at: https://developer.kx.com/products/kdb-x/install"
   Then stop.
3. Display the result:

**Exit code:** `<exit_code>`

**Output:**
```
<stdout>
```

If stderr is non-empty, also show:

**Stderr:**
```
<stderr>
```

Do not diagnose or fix errors — the user is in control. For debugging, use `/q-debug`.

**Pipeline note:** if the code has a bare monadic `<verb><adverb><operand>` (e.g. `+/1 2 3`, `+\1 2 3`) and the result is a `'type`/`'/` error with `exit_code 0`, mention this is the known `run_q` stdin-pipeline limitation (fix: `(+/)1 2 3` or `+/[1 2 3]`) — see CLAUDE.md "Known pitfall". Still don't fix it; just flag it.
