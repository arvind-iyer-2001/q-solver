# q-solver

Claude Code skill + MCP server for solving, running, and debugging q/kdb+ code using a persistent Docker container.

## What it does

Three Claude Code skills backed by a Python MCP server that manages a Docker container running q/kdb+:

| Skill | Purpose |
|-------|---------|
| `/q-run` | Run arbitrary q code immediately, show raw output |
| `/q-solve` | Solve a q problem — generates test cases, verifies solution, debugs failures |
| `/q-debug` | Debug broken q code — diagnose error, fix, run, confirm |

## Architecture

```
Claude Code skill
    ↓  (calls MCP tool)
mcp/server.py  (FastMCP stdio server)
    ↓  (calls docker-py)
Docker container  (ubuntu:22.04 + kdb-x)
    ↓  (exec q binary)
/root/.kx/bin/q
```

The CLI (`q-solver install`) handles all one-time interactive setup. The MCP server is a stdio subprocess with no terminal access — it only executes q code.

## Prerequisites

- Python 3.10+
- Docker Engine running
- KX license key (base64) — get one at https://developer.kx.com/products/kdb-x/install
- Claude Code CLI

## Install

```bash
git clone https://github.com/arvind-iyer-2001/q-solver ~/q-solver
cd ~/q-solver
pip install -e .
q-solver install
```

`install` will:
1. Prompt for your KX license key (hidden input)
2. Save it to `~/.config/q-solver/config.json` (chmod 600)
3. Copy skills to `~/.claude/skills/`
4. Register the MCP server via `claude mcp add`
5. Verify the connection with `claude mcp list`

Then build the Docker image (takes a few minutes):

```bash
q-solver build
```

Restart Claude Code, then test:

```
/q-run 1+1
```

Expected output: `2`

## CLI commands

```
q-solver install [--build]   # set up everything; --build also builds Docker image
q-solver build               # build Docker image using stored license key
q-solver uninstall           # remove skills and MCP registration
q-solver status              # show install state
```

## Project structure

```
mcp/
  server.py            # FastMCP server — registers run_q, get_container_status, reset_session, get_logs
  docker_manager.py    # Docker image build, container lifecycle, q execution, license expiry
  credential_store.py  # config.json read/write/delete, chmod 600
  requirements.txt
q_solver/
  __main__.py          # CLI: install/build/uninstall/status
skills/
  q-run/SKILL.md
  q-solve/SKILL.md
  q-debug/SKILL.md
docker/
  Dockerfile           # reference only — image built from memory in docker_manager.py
tests/
  test_credential_store.py
  test_docker_manager.py
  test_cli.py
```

## Running tests

```bash
pytest tests/ -v
```

30 tests, all passing. Docker is mocked in tests — no container required to run the test suite.

## MCP tools

| Tool | Description |
|------|-------------|
| `run_q(code)` | Execute q code; returns `{stdout, stderr, exit_code}` |
| `get_container_status()` | Returns `{running: bool}` |
| `reset_session()` | Restart container for clean q state |
| `get_logs(lines=50)` | Last N lines of container logs |

## Known quirks

- The `/` character in q's `+/x` (fold) is misinterpreted as a comment when code is fed via stdin pipeline. Use `sum x` instead when writing q code through this tool.
- MCP registration uses `claude mcp add` (writes to `.claude.json`) not `settings.json` — the two locations are different.
- `q-solver install` must be re-run after `q-solver uninstall` to rebuild the Docker image.
