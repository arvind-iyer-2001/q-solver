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
uv run pytest tests/ -v   # 37 tests, Docker mocked
```

## q execution detail

Code is base64-encoded before being passed to the container to avoid shell quoting issues:

```python
b64 = base64.b64encode((code + "\n").encode()).decode()
cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | /root/.kx/bin/q -q"]
```

The `\n` appended before encoding is required — q needs a trailing newline to flush stdout.

## Known pitfall: `/` in q code via stdin pipeline

The `/` character in q adverbs like `+/x` (fold/over) gets misinterpreted as a q comment when code is fed through the stdin pipeline. Use `sum x` instead of `+/x` when writing q code through the MCP tool. This is a pipeline limitation, not a q bug — in a normal q session `+/x` works fine.

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

1. `q-solver install` → prompts license (getpass, hidden), saves to `~/.config/q-solver/config.json` (chmod 600), copies skills, pulls `qtpy6969/q-solver-mcp`, runs `claude mcp add` (docker-based), verifies with `claude mcp list`
2. `q-solver build` → builds Docker image with `install_kdb.sh -y --b64lic <key>`, starts container
3. `q-solver publish-mcp` → builds + pushes `qtpy6969/q-solver-mcp` (multi-arch via buildx, no license needed) — maintainer-only

## Test suite structure

- `tests/test_credential_store.py` — 7 tests, uses `tmp_path` to redirect config paths
- `tests/test_docker_manager.py` — 22 tests, Docker fully mocked via monkeypatch
- `tests/test_cli.py` — 8 tests, subprocess.run mocked for MCP registration tests

## Dependencies

- `mcp>=1.0.0` — FastMCP (stdio server)
- `docker>=7.0.0` — docker-py for container management
- `pytest`, `pytest-mock` — dev dependency group (`uv run pytest`)

## Package install note

CLI install: `uv tool install --editable .` — editable so `__file__` in `q_solver/__main__.py` resolves to the source directory. Non-editable install breaks `_PKG_DIR` path resolution for finding `mcp/credential_store.py`.
