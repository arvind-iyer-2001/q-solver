---
name: q-debug
description: Debug broken q/kdb+ code — diagnose error, propose fix, run it, confirm it works
---

# q-debug

Debug broken q code. Diagnose, fix, verify.

## Not Initialized

If `run_q` raises an error mentioning "q-solver install", tell the user:
> "Q Solver is not set up yet. Run `q-solver install` in your terminal.
> Get your KX license at: https://developer.kx.com/products/kdb-x/install"
Then stop.

## Debug Loop

### Step 1 — Analyze

Read the code and any error or expected behavior description the user provided.

Identify:
- Error type: syntax error, type error, runtime error, wrong output
- Root cause: what specifically is wrong and why
- What the code is trying to accomplish

For `'type` / `'rank` / `'assign` / `'length` / `'domain` etc., load `q-knowledge:q`'s `references/common-errors.md` for the cause/fix table.

**Known parser quirks:** if the code has a **bare monadic `<verb><adverb><operand>`** at the start of an expression (e.g. `+/1 2 3`, `&/1 2 3`, `+\1 2 3`, `,/(...)`) and the failure is a `'/` (or `'type`) error that doesn't match the code's logic, this is a known kdb+ parser quirk for that token shape via `run_q` — not a bug in the code. Fix by parenthesizing/bracketing: `(+/)1 2 3` or `+/[1 2 3]`. Dyadic forms (`x f/ y`, `x f/: y`) and `each`/`'` are unaffected.

Same for **bare monadic `,x` (enlist) anywhere** — `,5`, `(,5)`, or inside a called function body — fails with `',`; **parens don't fix it**, only `enlist x` does. Dyadic `,` (`x,y`) is fine.

**Truncated-output red flag:** if `stdout` looks empty/cut-off and `stderr` shows a *single* `'/` or `',` error pointing at code that looks correct, the script likely halted early — search the *whole* script (including function bodies that get called) for any bare `,x` or unparenthesized fold/scan/raze adverb, not just the line in the error. See CLAUDE.md "Known pitfall".

### Step 2 — Propose fix

State clearly:
- **Root cause:** one sentence
- **Fix:** the corrected code in a code block, with a brief note on what changed

### Step 3 — Run fixed code

Call `run_q` with the fixed code.

### Step 4 — Evaluate

**If exit_code = 0:**
Present the fix as confirmed.

**If still failing:**
Show the user:
- New failure reason (exact stderr / stdout)
- Updated diagnosis
- Next proposed fix

Decide:
- **Fixable:** apply next fix, back to Step 3
- **Stuck:** explain what you know about the problem, ask the user for guidance

## Output (success)

**Root cause:** `<one-sentence diagnosis>`

**Fix:**
```q
<fixed code>
```

**Verified:** Runs successfully

**Output:**
```
<stdout from run>
```
