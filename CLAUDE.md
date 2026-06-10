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

Code is base64-encoded before being passed to the container to avoid shell quoting issues:

```python
b64 = base64.b64encode((code + "\n").encode()).decode()
cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | /root/.kx/bin/q -q"]
```

The `\n` appended before encoding is required — q needs a trailing newline to flush stdout.

## Known pitfall: `/` in q code via stdin pipeline

A **bare monadic `<verb><adverb><operand>`** at the start of an expression — `+/1 2 3`, `&/1 2 3`, `+\1 2 3`, `*/1 2 3`, etc. — gets misparsed when code is fed through the stdin pipeline, throwing a spurious `'type` (or `'/`) error with `exit_code 0`.

**Fix: parenthesize or bracket the verb-adverb** — `(+/)1 2 3` or `+/[1 2 3]` instead of `+/1 2 3`. This works for *any* verb/adverb combo, including custom dyadic functions in folds/scans (`{x,", ",y}/strs`), so it's the general fix. Named equivalents (`sum`/`prd`/`min`/`max`/`sums`/`prds`/`mins`/`maxs`/`deltas`) also work for the built-in cases.

**Unaffected:** dyadic adverb forms (`x f/ y`, `x f/: y`, `x f\: y`) and `each`/`'`. This is a pipeline limitation, not a q bug — in a normal q session `+/x` works fine.

The `q-solve`/`q-debug`/`q-run` skills document this caveat inline; `q-knowledge:q` (idiom/error reference) is unaware of it, so don't rely on its adverb examples verbatim through `run_q`.

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
