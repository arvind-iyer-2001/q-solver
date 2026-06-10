# q-solver

[![CI](https://github.com/arvind-iyer-2001/q-solver/actions/workflows/ci.yml/badge.svg)](https://github.com/arvind-iyer-2001/q-solver/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
q-solver-mcp container  (FastMCP stdio server, docker.sock mounted)
    ↓  (docker-py, against host Docker daemon)
kdb-x-runner container  (qtpy6969/kdb-x-runner — ubuntu:22.04 + kdb-x binary)
    ↓  (exec q binary)
/root/.kx/bin/q
```

The CLI (`q-solver install`) handles all one-time interactive setup. The MCP server itself runs inside a small container ([`qtpy6969/q-solver-mcp`](https://hub.docker.com/r/qtpy6969/q-solver-mcp)) registered via `claude mcp add q-solver docker -- run -i --rm ...`. It mounts the host's Docker socket (`/var/run/docker.sock`) to manage `kdb-x-runner` as a sibling container, and mounts `~/.config/q-solver` for the license/credential store. No host Python install is needed to *run* the MCP server — only Docker.

The `kdb-x-runner` container is a pre-built image ([`qtpy6969/kdb-x-runner`](https://hub.docker.com/r/qtpy6969/kdb-x-runner)) with the kdb-x binary installed but no license. `q-solver build` pulls the image and injects your license key (`kc.lic`) at runtime — no slow local build required.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (for installing the `q-solver` CLI — the MCP server itself runs in Docker)
- Docker Engine running
- KX license key (base64) — get one at https://developer.kx.com/products/kdb-x/install
- Claude Code CLI

## Install

```bash
git clone https://github.com/arvind-iyer-2001/q-solver
cd q-solver
uv tool install --editable .
q-solver install --build
```

`install --build` will:
1. Prompt for your KX license key (hidden input)
2. Save it to `~/.config/q-solver/config.json` (chmod 600)
3. Copy skills to `~/.claude/skills/`
4. Pull `qtpy6969/q-solver-mcp` from Docker Hub
5. Register the MCP server via `claude mcp add` (runs the pulled image, mounting `/var/run/docker.sock` and `~/.config/q-solver`)
6. Verify the connection with `claude mcp list`
7. Pull `qtpy6969/kdb-x-runner` from Docker Hub and inject your license (fast — no local build)

Restart Claude Code, then test:

```
/q-run 1+1
```

Expected output: `2`

## CLI commands

```
q-solver install [--build]   # set up everything; --build also builds Docker image
q-solver build               # build Docker image using stored license key
q-solver publish [--tag TAG]      # build + push multi-arch kdb-x-runner image to Docker Hub
q-solver publish-mcp [--tag TAG]  # build + push multi-arch q-solver-mcp image to Docker Hub
q-solver uninstall           # remove skills and MCP registration
q-solver status              # show install state
```

## Project structure

```
q_solver/
  __main__.py          # CLI: install/build/uninstall/status
  mcp/
    server.py          # FastMCP server — registers run_q, get_container_status, reset_session, get_logs
    docker_manager.py  # Docker image build, container lifecycle, q execution, license expiry
    credential_store.py  # config.json read/write/delete, chmod 600
  skills/
    q-run/SKILL.md
    q-solve/SKILL.md
    q-debug/SKILL.md
  docker/
    Dockerfile         # multi-stage build for qtpy6969/kdb-x-runner (license stripped)
    Dockerfile.mcp     # build for qtpy6969/q-solver-mcp (the MCP server image)
tests/
  test_credential_store.py
  test_docker_manager.py
  test_cli.py
```

## Running tests

```bash
uv run pytest tests/ -v
```

69 tests, all passing. Docker is mocked in tests — no container required to run the test suite.

## Linting

```bash
uv run ruff check .
```

Pre-commit hooks run ruff automatically on `git commit`. Set up once with:

```bash
uv run pre-commit install
```

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
- After `q-solver uninstall`, run `q-solver install --build` to reinstall everything including the Docker image.
- The MCP server container mounts `/var/run/docker.sock` so it can manage `kdb-x-runner` as a sibling container. This grants it root-equivalent control over the host's Docker daemon — standard for Docker-management MCP servers, but worth knowing.
