# `run_q` manual test matrix

Consolidated record of the ad-hoc `run_q` probes run during the 2026-06-11
investigation into `run_q` parser quirks (kdb+ 5.0, `.z.K`=`5f`,
`.z.k`=`2026.05.01`). Each case shows the q snippet, the observed
`exit_code`/`stdout`/`stderr`, and what it demonstrates. Cross-references are
to `CLAUDE.md` → "Known pitfall: monadic `/`, `\`, `,` ... misparse" and "q
execution detail".

## How to reproduce

Any case can be re-run directly against the container:

```python
import sys
sys.path.insert(0, "q_solver/mcp")
import docker_manager
print(docker_manager.run_q("<code here>"))
```

or via the `mcp__q-solver__run_q` tool / `/q-run` skill with the same code.

## Generic parse-error shape

All `'/` and `',` cases below share this stderr shape (`exit_code: 1`,
`stdout: ""`):

```
'<ISO-8601 timestamp> <bad-token>
  [2]  /tmp/q_solver_<uuid>.q:<line>: <source line>
                                       ^
```

Below, "stderr: `'/`" / "stderr: `',`" means stderr matches this shape with
that bad token.

## 1. `/`-fold, `\`-scan, `,/`-raze — bare monadic vs fixed

Tests: CLAUDE.md "`/`-fold, `\`-scan, `,/`-raze: bare monadic
`<verb><adverb><operand>`".

| Code | exit_code | stdout | stderr | Notes |
|---|---|---|---|---|
| `+/1 2 3` | 1 | `""` | `'/` | bare fold — fails |
| `(+/)1 2 3` | 0 | `"6\n"` | `""` | parens — fix |
| `+/[1 2 3]` | 0 | `"6\n"` | `""` | brackets — fix |
| `&/1 2 3` | 1 | `""` | `'/` | bare fold, different verb — same failure |
| `*/1 2 3` | 1 | `""` | `'/` | bare fold, different verb — same failure |
| `+\1 2 3` | 1 | `""` | `'/` | bare scan — same failure class |
| `,/(1 2;3 4)` | 1 | `""` | `'/` | bare raze — same failure class |
| `raze(1 2;3 4)` | 0 | `"1 2 3 4\n"` | `""` | named equivalent — fix |
| `sum 1 2 3` | 0 | `"6\n"` | `""` | named equivalent — fix |

## 2. Custom dyadic function in a fold — bare vs parenthesized

Tests: same section, "works for any verb/adverb combo, including custom
dyadic functions in folds".

| Code | exit_code | stdout | stderr | Notes |
|---|---|---|---|---|
| `` {x,", ",y}/("a";"b";"c") `` | 1 | `""` | `'/` | bare custom-function fold — fails |
| `` ({x,", ",y}/)("a";"b";"c") `` | 0 | `"a, b, c\n"` | `""` | parens — fix |

## 3. `,` (enlist) misparse — parens do NOT help

Tests: CLAUDE.md "`,` (enlist): bare monadic `,x` anywhere — parens do NOT
help". Every failing form below has `exit_code: 1`, `stdout: ""`,
`stderr: '<,>` (the generic shape, bad token `,`).

### Failing forms (all `',`, regardless of context)

| Code | Notes |
|---|---|
| `,5` | bare enlist of a literal |
| `,1 2 3` | bare enlist of a list |
| `(,5)` | **parenthesized — still fails**, parens don't fix `,` |
| `,()` | enlist of empty list |
| `,(1+1)` | enlist of a parenthesized expression |
| `a:,5` | assignment RHS |
| `f[,5]` | as a function-call argument |
| `{,x}5` | inside a *called* lambda body |
| `x:5` then `,x` | enlist of a variable, not just a literal |
| `` ([] c:,5) `` | table column definition |

### Working forms (the fix)

| Code | exit_code | stdout | stderr | Notes |
|---|---|---|---|---|
| `enlist 5` | 0 | `",5\n"` | `""` | `enlist x` is the drop-in replacement for `,x` (note: q *displays* a 1-item list as `,5` — that's normal output, not an error) |
| `1,2` | 0 | `"1 2\n"` | `""` | dyadic `,` (concat) is unaffected |
| `{x,1}5` | 0 | `"5 1\n"` | `""` | dyadic `,` inside a lambda is unaffected |
| `` ([] c:enlist 5) `` | 0 | table output | `""` | `enlist` fixes the table-column case |
| `raze(1 2;3 4)` | 0 | `"1 2 3 4\n"` | `""` | `raze` is the named fix for `,/` (see §1) |

## 4. Genuine error types — `exit_code` reliability (Core gap #3)

Tests: CLAUDE.md "q execution detail" — confirms `exit_code` is now a
reliable 0/1 signal for real q errors (not just the `/`/`,` parser quirks
above), which the temp-file rewrite (PR #12) was meant to guarantee.

| Code | exit_code | stdout | stderr | Notes |
|---|---|---|---|---|
| `1+1` | 0 | `"2\n"` | `""` | baseline sanity |
| `` 1+`a `` | 1 | `""` | `'type` | type error |
| `(1 2)+1 2 3` | 1 | `""` | `'length` | length/rank mismatch |
| `undefinedVar123` | 1 | `""` | `'undefinedVar123` | undefined-variable error |

## 5. Multi-line script — abort on first error (truncated stdout)

Tests: CLAUDE.md "Practical impact: one bad token kills the rest of the
script" and "Script halts on first error".

```q
1+1
,5
2+2
```

- exit_code: `1`
- stdout: `"2\n"` — only line 1's result; line 3 (`2+2`) never runs
- stderr: `'/` (well actually `',`, bad token `,`) pointing at line 2

Demonstrates: a single misparsing token anywhere in a script (even one that
looks fine in isolation) silently truncates everything after it — the rest
of the script's output is simply missing, with no indication beyond the one
stderr line.

## 6. Persistent session check (Core gap #4)

Tests: confirms each `run_q` call is a fresh `q` process — no variable state
survives between calls. Two separate `run_q` calls:

| Call | Code | exit_code | stdout | stderr |
|---|---|---|---|---|
| 1 | `x:42` | 0 | `""` | `""` |
| 2 | `x` | 1 | `""` | `'x` (undefined variable) |

`x` set in call 1 is gone by call 2 — each call starts a brand-new `q`
process with no shared state. Not fixed; tracked as Core gap #4 in
`HANDOFF.md`.
