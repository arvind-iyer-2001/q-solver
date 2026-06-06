# Persistent q Sessions — Design Spec

**Date:** 2026-06-06  
**Status:** Approved

## Overview

Add persistent q/kdb+ sessions to the q-solver MCP server. Each session is a long-lived q process running inside the `kdb-x-runner` container on a dedicated TCP port. Multiple sessions can run concurrently, each with its own namespace. Sessions expire after 10 minutes of idle time but auto-resurrect on next use (same session_id, fresh state).

Stateless `run_q` remains unchanged for throwaway one-off runs.

---

## Architecture

```
MCP tools (server.py)
    ↓
SessionManager (session_manager.py)   ← new
    ↓
docker_manager.py  (session start/kill added)
    ↓
kdb-x-runner container
    ├── tail -f /dev/null  (keepalive, unchanged)
    ├── q -p 5001 -q       (session "analysis")
    ├── q -p 5002 -q       (session "homework")
    └── ...
```

`SessionManager` is a singleton instantiated at server boot. All session state is in-memory — MCP server restart clears all sessions (container keeps running independently). A background daemon thread checks expiry every 60 seconds.

---

## Session Data Model

```python
@dataclass
class QSession:
    session_id: str        # UUID4
    group: str | None      # optional label
    port: int              # 5001–5099
    created_at: float      # epoch
    last_activity: float   # epoch, updated on every run
    status: str            # "running" | "expired"
```

**Port pool:** 5001–5099 (100 concurrent sessions max).

**Expiry flow:**
1. Background thread detects `now - last_activity > 600s`
2. Kill q process: `pkill -f "q -p {port}"`
3. Set `status = "expired"` — session_id stays registered
4. Next `run_q_in_session` call: spawn fresh q on same port, reset timestamps, set `status = "running"`, include `was_restarted: true` in response

---

## MCP Tools

### New tools

```
create_session(group: str = None) → {session_id, group, port, created_at}
```
Starts a q process on the next available port. Returns session_id for use in subsequent calls.

```
run_q_in_session(session_id: str, code: str) → {stdout, stderr, exit_code, was_restarted: bool}
```
Runs code in the named session's q namespace. If session was expired, silently resurrects it first.

```
expire_session(session_id: str) → {ok: bool}
```
Immediately kills the session's q process. Session_id remains valid (auto-resurrects on next use).

```
list_sessions() → [{session_id, group, status, idle_seconds, created_at}]
```
Returns all registered sessions including expired ones.

### Unchanged

```
run_q(code: str) → {stdout, stderr, exit_code}
```
Stateless throwaway run. No session involved.

---

## IPC — q-talks-to-q Relay

**Start session:**
```bash
docker exec -d kdb-x-runner bash -c "nohup q -p {port} -q </dev/null &>/dev/null &"
```

**Run code in session** (base64-encoded relay to avoid shell quoting):
```python
relay = f'h:hopen {port}; -1 string h "{escaped_code}"; hclose h'
b64 = base64.b64encode((relay + "\n").encode()).decode()
cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | q -q"]
container.exec_run(cmd, demux=True)
```
Ephemeral q client connects to session port, runs code in that namespace, prints result, exits. Session q process retains all state.

**Kill session:**
```bash
docker exec kdb-x-runner bash -c "pkill -f 'q -p {port}'"
```

**Limitation:** Results coerced to string via `string`. Tables print as text. Acceptable since skills display output as text.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Unknown session_id | `RuntimeError: "session not found: {session_id}"` |
| Session expired, next call | Silently resurrect, `was_restarted: true` |
| Port collision on start | Retry next port, up to 10 attempts |
| q fails to start | `RuntimeError: "failed to start session on port {port}"` |
| Container not running | `ensure_container_running()` handles it |
| All 100 ports exhausted | `RuntimeError: "session limit reached (100)"` |
| q process crashes mid-session | Next call detects port not listening → auto-resurrect |

---

## Files Changed

| File | Change |
|------|--------|
| `q_solver/mcp/session_manager.py` | New — `QSession` dataclass, `SessionManager` class |
| `q_solver/mcp/docker_manager.py` | Add `start_session_process`, `kill_session_process` |
| `q_solver/mcp/server.py` | Add 4 new MCP tools |
| `tests/test_session_manager.py` | New — 9 tests, Docker mocked |

---

## Tests

| Test | Verifies |
|------|----------|
| `test_create_session_allocates_port` | Returns session_id, port in 5001–5099 |
| `test_create_session_with_group` | Group stored on session |
| `test_run_in_session_updates_last_activity` | Timestamp updated per run |
| `test_expire_session_kills_process` | pkill called, status → expired |
| `test_list_sessions_returns_all` | All sessions including expired |
| `test_expired_session_resurrects_on_run` | was_restarted: true, fresh process |
| `test_session_limit_raises` | 100 sessions → RuntimeError |
| `test_unknown_session_id_raises` | Unknown ID → RuntimeError |
| `test_background_thread_expires_idle` | Idle >600s → status expired |

Existing 31 tests untouched.
