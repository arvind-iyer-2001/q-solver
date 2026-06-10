# q-solver — Claude Code guidance

## What this project is

A dockerized MCP server (Python/FastMCP) + three Claude Code skills for running q/kdb+ code in a persistent Docker container. The CLI (`q-solver install`) handles one-time setup. The MCP server itself runs as a container (`qtpy6969/q-solver-mcp`), with the host's Docker socket mounted in so it can manage the `kdb-x-runner` container as a sibling.

## Architecture rules

- **CLI only reads user input.** MCP servers run as stdio subprocesses — no terminal access, no `input()` calls in `mcp/`.
- **Skills handle AI reasoning.** MCP server handles Docker. Never put q reasoning logic in `mcp/server.py`.
- **credential_store is in `mcp/`** so both `docker_manager.py` and the CLI can import it via sys.path manipulation.
- **`mcp/*.py` must run standalone inside the `q-solver-mcp` image** — no imports outside `mcp/`, since `Dockerfile.mcp` only copies `mcp/*.py` into the image.

## Key files

| File | Role |
|------|------|
| `mcp/server.py` | FastMCP server entry point |
| `mcp/docker_manager.py` | All Docker operations + q execution |
| `mcp/credential_store.py` | License key storage, chmod 600 |
| `q_solver/__main__.py` | CLI: install/build/publish/publish-mcp/uninstall/status |
| `docker/Dockerfile` | builds `qtpy6969/kdb-x-runner` (q/kdb+ runtime) |
| `docker/Dockerfile.mcp` | builds `qtpy6969/q-solver-mcp` (the MCP server itself) |
| `skills/*/SKILL.md` | Claude Code skill definitions |

## Running tests

```bash
uv run pytest tests/ -v   # 76 tests, Docker mocked
```

## q execution detail

Code is base64-encoded and written to a temp script file inside the container, then run as `q <file> -q` (NOT piped to `q -q` on stdin — see below for why):

```python
b64 = base64.b64encode((code + "\n").encode()).decode()
script_path = f"/tmp/q_solver_{uuid.uuid4().hex}.q"
cmd = [
    "bash", "-c",
    f"base64 -d <<< '{b64}' > {script_path} && {Q_BINARY} {script_path} -q < /dev/null; "
    f"ec=$?; rm -f {script_path}; exit $ec",
]
```

The `\n` appended before encoding is required — q needs a trailing newline to flush stdout.

**Flag order matters**: `q <file> -q` (flag *after* the script path). `q -q <file>` silently swallows the file argument — the script never loads, no output, no error, `exit_code 0`. Always put `-q` last.

This temp-file approach (vs. the old `base64 -d <<< ... | q -q` pipe) makes `exit_code` a reliable error signal: q errors (`'type`, `'rank`, `'/`, etc.) now produce `exit_code 1` and land on stderr; success is `exit_code 0`. With the old pipe approach, `exit_code` was *always* 0 regardless of errors.

**Script halts on first error**: `q file.q -q` loads the script top-to-bottom; an uncaught error on any line aborts all remaining lines — no further stdout is produced. Combined with the parser quirks below, a single misparsing token *anywhere* in a multi-statement script (even inside a called function body) truncates everything after it. See "Known pitfall".

## Known pitfall: monadic `/`, `\`, `,` (overloaded operator chars) misparse — `'/`, `',`, `'type` errors

### `/`-fold, `\`-scan, `,/`-raze: bare monadic `<verb><adverb><operand>`

A **bare monadic `<verb><adverb><operand>`** at the start of an expression — `+/1 2 3`, `&/1 2 3`, `+\1 2 3`, `*/1 2 3`, `,/(1 2;3 4)`, etc. — throws a spurious `'/` (or `'type`) parse error (`exit_code 1`).

**This is NOT a `run_q`-pipeline artifact** — verified empirically (2026-06-11) on kdb+ 5.0 (`.z.K`=`5f`, `.z.k`=`2026.05.01`): the identical error reproduces via stdin pipe (`... | q -q`), script-file execution (`q file.q -q`), and even under a pseudo-tty (`script -qec "q -q" /dev/null`). It appears to be an inherent kdb+ 5.0 parser characteristic for this token shape when not driven by an interactive keystroke-by-keystroke reader (linenoise) — there is no fix available at the `run_q`/wrapper level.

**Fix: parenthesize or bracket the verb-adverb** — `(+/)1 2 3` or `+/[1 2 3]` instead of `+/1 2 3`. This works for *any* verb/adverb combo, including custom dyadic functions in folds/scans (`{x,", ",y}/strs`), so it's the general fix. Named equivalents (`sum`/`prd`/`min`/`max`/`sums`/`prds`/`mins`/`maxs`/`deltas`/`raze`) also work for the built-in cases.

**Unaffected:** dyadic adverb forms (`x f/ y`, `x f/: y`, `x f\: y`) and `each`/`'`.

### `,` (enlist): bare monadic `,x` anywhere — parens do NOT help

A **monadic `,x`** (enlist) — `,5`, `,1 2 3`, `(,5)`, `,()`, a table column `c:,5`, or even inside a *called* lambda body (`{,x}5`) — throws the same `'<,>` parse error (`exit_code 1`).

Verified empirically (2026-06-11): unlike the `/`-fold case, **parenthesizing does not fix this** — `(,5)` still errors. Pre-existing in the old pipe approach too (not introduced by the temp-file rewrite), but the old approach masked it (REPL continued past the error with `exit_code 0`).

**Fix: use `enlist x` instead of `,x`** — always, in every position. `enlist` is a drop-in replacement with identical semantics.

**Unaffected:** dyadic `,` (`x,y`, `1,2`, `{x,1}5`).

### Practical impact: one bad token kills the rest of the script

Because script execution halts on the first uncaught error, and `,x`/bare-`/`-folds/`,/`-raze are everyday idiomatic q, **a single occurrence anywhere — even deep inside a called function — silently truncates all output after it**, leaving only that one error on stderr (`exit_code 1`). Example: `1+1\n,5\n2+2` -> stdout `"2\n"` only; line 3 never runs.

**Recommendation for AI-generated q code via `run_q`:** always use `enlist x` (never `,x`), always use `raze x` (never `,/x`), and always parenthesize/bracket/name fold-scan adverbs (`(+/)x`, `+/[x]`, `sum x` — never bare `+/x`).

The `q-solve`/`q-debug`/`q-run` skills document these caveats inline; `q-knowledge:q` (idiom/error reference) is unaware of them, so don't rely on its `,`/adverb examples verbatim through `run_q`.

## MCP registration

`q-solver install` uses `claude mcp add` (not direct `settings.json` editing). The server is registered in `~/.claude.json` under the project entry as a `docker run` command (see `_mcp_docker_args()` in `q_solver/__main__.py`):

```
claude mcp add q-solver docker -- run -i --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/.config/q-solver:/root/.config/q-solver \
  qtpy6969/q-solver-mcp:latest
```

The `settings.json` `mcpServers` key is ignored by Claude Code CLI.

## Install flow

1. `q-solver install` → prompts license (getpass, hidden), saves to `~/.config/q-solver/config.json` (chmod 600), copies skills, ensures `q-knowledge@kx-skills` plugin is installed (`_ensure_q_knowledge_plugin()` — adds the `kx-skills` marketplace + installs the plugin if missing), pulls `qtpy6969/q-solver-mcp`, runs `claude mcp add` (docker-based), verifies with `claude mcp list`
2. `q-solver build` → builds Docker image with `install_kdb.sh -y --b64lic <key>`, starts container
3. `q-solver publish-mcp` → builds + pushes `qtpy6969/q-solver-mcp` (multi-arch via buildx, no license needed) — maintainer-only

## Test suite structure

- `tests/test_credential_store.py` — 7 tests, uses `tmp_path` to redirect config paths
- `tests/test_docker_manager.py` — 28 tests, Docker fully mocked via monkeypatch
- `tests/test_cli.py` — 37 tests, subprocess.run mocked for MCP/plugin registration tests
- `tests/test_server.py` — 4 tests, FastMCP tool registration

## Dependencies

- `mcp>=1.0.0` — FastMCP (stdio server)
- `docker>=7.0.0` — docker-py for container management
- `pytest`, `pytest-mock` — dev dependency group (`uv run pytest`)

## Package install note

CLI install: `uv tool install --editable .` — editable so `__file__` in `q_solver/__main__.py` resolves to the source directory. Non-editable install breaks `_PKG_DIR` path resolution for finding `mcp/credential_store.py`.
