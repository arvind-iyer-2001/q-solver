---
name: generate-kxnb
description: Use when asked to generate, build, or export a kx-vscode .kxnb notebook — from an instruction describing what the notebook should contain, a problem to solve, or this conversation's q code/run_q results
---

# generate-kxnb

Turn a set of instructions (or this conversation) into a `.kxnb` file — the
JSON notebook format used by the [kx-vscode](https://github.com/KxSystems/kx-vscode)
extension. The instruction is the source of truth for *what cells to create*;
this skill only handles turning that content into valid kxnb JSON.

## kxnb format

A `.kxnb` file is JSON: `{"cells": [...]}`. Per
[`notebookSerializer.ts`](https://github.com/KxSystems/kx-vscode/blob/main/src/services/notebookSerializer.ts)
and `src/models/notebook.ts`, each cell:

```json
{
  "kind": 2,
  "value": "1+1",
  "languageId": "q",
  "outputs": [
    {"items": [{"data": "2\n", "mime": "text/plain"}]}
  ]
}
```

- `kind`: `1` = markdown (`vscode.NotebookCellKind.Markup`), `2` = code (`.Code`) — integers, not strings.
- `languageId`: `"markdown"` for markdown cells; `"q"` (also `"python"`/`"sql"`) for code cells.
- `outputs`: **required array, even when empty (`[]`)** — markdown cells always have `outputs:[]`.
- Optional cell fields `target` / `variable` (execution target / scratchpad var) — omit unless the user specifies them.

## Steps

1. **Figure out the cell list from the instruction.** Sources, in priority order:
   - If the instruction describes a notebook to build ("make a notebook that does X, then Y, then Z"), turn each logical step into a markdown cell (what/why) + a code cell (the q/python/sql for that step).
   - If the instruction is "export this chat/session", use the q code blocks and `run_q`/`/q-run`/`/q-solve`/`/q-debug` results already in the conversation, in the order they were discussed.
   - If the instruction gives a problem to solve, write the solving q code yourself (idiomatic — load `q-knowledge:q` if needed) before building the cell.
2. For each step, build:
   - a markdown cell (`kind:1`, `outputs:[]`) with brief context. Keep it terse; for "export this chat" mirror what was actually discussed, don't invent detail.
   - a code cell (`kind:2`, `languageId` matching the language, default `"q"`) with `value` = the source for that step.
3. **Populate `outputs`:**
   - If the conversation already has a `run_q` result for that exact code, use its `stdout`/`stderr`.
   - Else, if a result is needed and the q-solver container is available, call `run_q` to get one.
   - Otherwise leave `outputs:[]` — don't fabricate output.
   - When used: one item `{"data": "<stdout>", "mime": "text/plain"}`; if `stderr` non-empty, add a second item `{"data": "STDERR:\n<stderr>", "mime": "text/plain"}`.
4. Assemble `{"cells": [...]}` and write it with a script (e.g. Python `json.dump`) — **never hand-build the JSON string**; embedded `\n` and quotes in code or error text break manual escaping.
5. Validate by re-parsing the written file with `json.load` and checking `cells` is a list of dicts each containing `kind`, `value`, `languageId`, `outputs`.
6. If the user didn't give a save path, ask (default: current directory, filename `<topic>.kxnb`). Report the path, cell count, and that it opens in VS Code with the kx-vscode extension installed.

## Common mistakes

- `outputs` missing or `null` on markdown cells — must be `[]`.
- `kind` written as the strings `"markdown"`/`"code"` instead of the integers `1`/`2`.
- Skipping the re-parse validation step — malformed JSON fails silently when opened in the extension.
- Fabricating `stdout` for code that was never actually run.
