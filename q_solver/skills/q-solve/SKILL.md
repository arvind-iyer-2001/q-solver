---
name: q-solve
description: Solve a q/kdb+ question — generate solution, run it against test cases, debug failures with the user in the loop, surface only verified answers
---

# q-solve

Solve a q/kdb+ question with verified output.

## Not Initialized

If `run_q` raises an error mentioning "q-solver install", tell the user:
> "Q Solver is not set up yet. Run `q-solver install` in your terminal.
> Get your KX license at: https://developer.kx.com/products/kdb-x/install"
Then stop.

## Solve Loop

### Step 1 — Analyze

Read the question. Identify expected input/output types and edge cases.

**If test cases are provided by the user:** use them as-is.

**If no test cases are provided:** generate test cases covering:
- Happy path (typical input)
- Empty or null input (e.g. `()`, `0N`)
- Type edge cases (e.g. single item vs list, integer vs float)

Present the generated test cases to the user with a one-line explanation for each. Wait for the user to accept or request changes before proceeding.

### Step 2 — Generate solution

Load the `q-knowledge:q` skill for idiomatic q (vectorization, type traps, error patterns). Be idiomatic: use q primitives and vector operations. Avoid unnecessary loops.

**Pipeline caveat:** `run_q` pipes code through `base64 | q -q` on stdin, which misparses a **bare monadic `<verb><adverb><operand>`** at the start of an expression (e.g. `+/1 2 3`, `&/1 2 3`, `+\1 2 3`) — throws a spurious `'type` (or `'/`) error with `exit_code 0`. Dyadic forms (`x f/ y`, `x f/: y`, `x f\: y`) and `each`/`'` are unaffected. Fix by **parenthesizing or bracketing the verb-adverb**: `(+/)1 2 3` or `+/[1 2 3]` instead of `+/1 2 3` — works for any verb/adverb combo, including custom dyadic functions in folds (`{x,", ",y}/strs`). Named equivalents (`sum`/`prd`/`min`/`max`/`sums`/`prds`/`mins`/`maxs`/`deltas`) also work. See CLAUDE.md "Known pitfall".

### Step 3 — Run

Build a q script that:
1. Defines your solution function
2. Runs each test case and checks the result
3. Signals failure with `'"FAIL: ..."` (q signal) on mismatch

Example test harness:
```q
myFunc:{[x] x+1}

/ test: increments single value
if[not myFunc[1] = 2; '"FAIL: expected 2, got ", string myFunc[1]]

/ test: empty list returns empty list
if[not myFunc[`int$()] ~ `int$(); '"FAIL: empty list"]
```

Call `run_q` with this script.

### Step 4 — Evaluate

**If exit_code = 0 and no `'FAIL` or error in output:**
Solution is verified. Present it.

**If exit_code ≠ 0 or error detected:**
Surface to the user:
- Your attempted solution (code block)
- Failure reason (exact stderr / stdout error)
- Your diagnosis of what went wrong
- Your proposed fix (code block)

Then decide:
- **Fixable:** apply the fix, go back to Step 3
- **Stuck:** tell the user you cannot determine the fix and ask for guidance

## Output (success)

**Solution:**
```q
<solution code>
```

**Test cases:**
- `<test case 1 description>`
- `<test case 2 description>`

**Verified:** All tests passed

**How it works:**
<one paragraph explanation>
