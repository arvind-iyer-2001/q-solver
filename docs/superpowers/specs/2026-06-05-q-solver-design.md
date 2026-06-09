# Q Solver — Design Spec

**Date:** 2026-06-05  
**Status:** Approved

---

## Overview

Q Solver is a Claude Code–native system for solving, running, and debugging q/kdb+ code. It consists of:

- A Python MCP server that manages a persistent Docker container running q/kdb+
- Three Claude Code skills: `/q-solve`, `/q-run`, `/q-debug`

The system generates verified answers — it runs every solution, debugs failures transparently with the user in the loop, and only surfaces confirmed-correct output.

---

## Architecture

```
Claude Code (user)
      │
      ├── /q-solve skill
      ├── /q-run skill
      └── /q-debug skill
              │
              ▼
    MCP Server (Python, mcp SDK + docker-py)
    ~/.config/q-solver/
    ├── config.json         ← credentials + container name
    └── server.py
              │
              ▼
    Docker Container (persistent, named "q-solver")
    └── q/kdb+ installed via install_kdb.sh
```

**MCP tools:**

| Tool | Signature | Description |
|------|-----------|-------------|
| `run_q` | `(code: str) → {stdout, stderr, exit_code}` | Execute q code in container |
| `get_container_status` | `() → {running: bool}` | Health check |
| `reset_session` | `() → bool` | Restart container for clean slate |
| `get_logs` | `(lines: int) → str` | Tail container logs |

Skills never call Docker directly — all execution goes through MCP tools.

---

## Skills

### `/q-solve <question>`

Full solve loop for q/kdb+ questions. Accepts question text with optional inline test cases.

**Output:** verified solution, test cases used or generated, explanation of approach.

### `/q-run <code>`

Thin scratch-pad wrapper. Paste q code, runs immediately via `run_q`. No solve loop, no test cases. Outputs raw stdout/stderr and exit code.

### `/q-debug <code>`

User pastes broken q code with optional description of expected behavior. Claude diagnoses, proposes fix, runs it. Same human-in-loop transparency as solve loop. Outputs root cause diagnosis, fixed code, and run confirmation.

---

## Solve Loop

```
/q-solve invoked
         │
         ▼
1. ANALYZE
   - Identify expected input/output types and edge cases
   - If test cases provided → use them
   - If not → generate test cases, explain each one to user,
     wait for user to accept/reject before proceeding
         │
         ▼
2. GENERATE — write q solution
         │
         ▼
3. RUN — call run_q(solution + test cases)
         │
    ┌────┴────┐
  PASS      FAIL
    │          │
    ▼          ▼
4. PRESENT   SURFACE to user:
   verified   - attempted solution
   answer     - failure reason / stderr
              - Claude's diagnosis
              - proposed fix
              │
              ▼
           Claude judges: fixable?
           ├── YES → loop back to step 2 with fix context
           └── NO  → surface "stuck" state, ask user for guidance
```

### Test Case Rules

- Generated test cases always shown with explanation before running
- Cases must cover: happy path, empty/null input, type edge cases
- User can add or reject generated cases before execution

---

## Credential & Container Bootstrap

### First Run

1. MCP server starts, checks `~/.config/q-solver/config.json`
2. File missing or incomplete → prompt user:

   ```
   Q Solver needs your KX license.
   Get it at: https://developer.kx.com/products/kdb-x/install

   Enter LICENSE_KEY (base64): _
   ```

3. Save license to `config.json` (chmod 600)
4. Build Docker image `q-solver:latest`:

   ```dockerfile
   FROM ubuntu:22.04
   RUN apt-get update && apt-get install -y curl unzip && \
       curl -sLO https://portal.dl.kx.com/assets/raw/kdb-x/install_kdb/~latest~/install_kdb.sh && \
       bash install_kdb.sh -y --b64lic <LICENSE_KEY>
   ```

   The script's `-y`/`--non-interactive` flag suppresses all prompts, auto-selects defaults, and disables telemetry. `--b64lic` passes the base64-encoded license. No `expect` or stdin tricks needed.

5. Start container named `q-solver`, persist name in `config.json`

### Subsequent Starts

- Check if `q-solver` container is running; start it if stopped
- Image rebuild only if missing or user explicitly requests reset

### License Expiry Handling

`run_q` inspects every response for license expiry signals in stderr (e.g. `'licexp`, `license expired`). On detection:

1. Delete `config.json`
2. Stop and remove `q-solver` container
3. Remove `q-solver:latest` image
4. Re-prompt user for fresh LICENSE_KEY (with URL above)
5. Rebuild image and restart container

This path is triggered transparently from any skill that calls `run_q`.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Container not running | Auto-start; surface error if start fails |
| q syntax error | Surface stderr, diagnose, propose fix |
| q runtime error | Surface stderr, diagnose, propose fix |
| License expired | Full credential reset flow (see above) |
| Docker not installed | Fatal error with install instructions |
| Image build fails | Surface build log, ask user to re-enter credentials |

---

## CLI Installer

A `q-solver` CLI tool handles all one-time setup interactively. It is the only component that prompts for user input — MCP servers run as stdio subprocesses and cannot read from a terminal.

```
q-solver install [--build]   prompt for license → save config → copy skills → register MCP
q-solver build               build Docker image using stored license key
q-solver uninstall           remove skills + MCP registration from Claude Code
q-solver status              show install state: skills, MCP, license, container
```

Install flow:
1. Print license URL: `https://developer.kx.com/products/kdb-x/install`
2. Prompt: `Enter LICENSE_KEY (base64):`
3. Save to `~/.config/q-solver/config.json` (chmod 600)
4. Copy `skills/*/SKILL.md` → `~/.claude/skills/*/SKILL.md`
5. Register MCP server in `~/.claude/settings.json` under `mcpServers`
6. If `--build`: build Docker image and start container immediately

The CLI is installed via `pip install -e .` from the project root.

---

## File Layout

```
q-solver/
├── q_solver/
│   ├── __init__.py         ← empty
│   └── __main__.py         ← CLI entry point (install/build/uninstall/status)
├── mcp/
│   ├── server.py           ← MCP server entry point
│   ├── docker_manager.py   ← container lifecycle
│   ├── credential_store.py ← config.json read/write
│   └── requirements.txt
├── skills/
│   ├── q-solve/
│   │   └── SKILL.md
│   ├── q-run/
│   │   └── SKILL.md
│   └── q-debug/
│       └── SKILL.md
├── docker/
│   └── Dockerfile
├── pyproject.toml
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-05-q-solver-design.md
```

---

## Out of Scope

- Web UI or REST API
- Multi-user or networked access
- Persistent q session state across container restarts (container restart = clean slate)
- Support for non-q KX products
