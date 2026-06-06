# Persistent q Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent named q sessions to the MCP server so state (variables, functions, tables) survives between `run_q_in_session` calls.

**Architecture:** Each session is a long-lived q process running inside the `kdb-x-runner` container on a dedicated TCP port (5001–5099). A Python `SessionManager` singleton manages session lifecycle. Code runs via a q-talks-to-q relay: an ephemeral q client connects to the session port via IPC, executes the code in that namespace, prints the string result, and exits.

**Tech Stack:** Python 3.11, docker-py, FastMCP, q IPC (`-p port`), base64 encoding, threading

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `q_solver/mcp/session_manager.py` | Create | `QSession` dataclass, `SessionManager` class, singleton `get_manager()` |
| `q_solver/mcp/docker_manager.py` | Modify | Add `start_session_process`, `kill_session_process`, `run_q_in_session_port` |
| `q_solver/mcp/server.py` | Modify | Add 4 new MCP tools wired to `SessionManager` |
| `tests/test_session_manager.py` | Create | 9 tests, all Docker mocked |

---

## Task 1: Add session process functions to docker_manager.py

**Files:**
- Modify: `q_solver/mcp/docker_manager.py`
- Test: `tests/test_docker_manager.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_docker_manager.py`:

```python
def test_start_session_process_calls_exec(mock_client):
    import docker_manager
    container = MagicMock()
    mock_client.containers.get.return_value = container
    docker_manager.start_session_process(container, 5001)
    container.exec_run.assert_called_once()
    call_args = container.exec_run.call_args[0][0]
    assert "5001" in " ".join(call_args)


def test_kill_session_process_calls_pkill(mock_client):
    import docker_manager
    container = MagicMock()
    docker_manager.kill_session_process(container, 5001)
    container.exec_run.assert_called_once()
    call_args = container.exec_run.call_args[0][0]
    assert "5001" in " ".join(call_args)


def test_run_q_in_session_port_returns_dict(mock_client):
    import docker_manager
    container = MagicMock()
    exec_result = MagicMock()
    exec_result.exit_code = 0
    exec_result.output = (b"4\n", b"")
    container.exec_run.return_value = exec_result
    container.put_archive.return_value = True
    result = docker_manager.run_q_in_session_port(container, 5001, "test-session-id", "1+3")
    assert result["exit_code"] == 0
    assert result["stdout"] == "4\n"
    assert result["stderr"] == ""
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_docker_manager.py::test_start_session_process_calls_exec tests/test_docker_manager.py::test_kill_session_process_calls_pkill tests/test_docker_manager.py::test_run_q_in_session_port_returns_dict -v
```

Expected: FAIL with `AttributeError: module 'docker_manager' has no attribute 'start_session_process'`

- [ ] **Step 3: Implement the three functions**

Add to `q_solver/mcp/docker_manager.py` after the `inject_license` function:

```python
def start_session_process(container, port: int) -> None:
    container.exec_run(
        ["bash", "-c", f"nohup q -p {port} -q </dev/null &>/dev/null &"],
        detach=True,
    )
    import time
    time.sleep(0.5)


def kill_session_process(container, port: int) -> None:
    container.exec_run(["bash", "-c", f"pkill -f 'q -p {port}' || true"])


def run_q_in_session_port(container, port: int, session_id: str, code: str) -> dict:
    code_bytes = code.encode()
    tmpfile_name = f"qcode_{session_id}.q"
    tmpfile_path = f"/tmp/{tmpfile_name}"

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=tmpfile_name)
        info.size = len(code_bytes)
        tar.addfile(info, io.BytesIO(code_bytes))
    tar_stream.seek(0)
    container.put_archive("/tmp/", tar_stream)

    relay = (
        f'h:hopen {port}; '
        f'code:"\\n" sv read0 `$":{tmpfile_path}"; '
        f'-1 string h code; '
        f'hclose h; '
        f'system "rm {tmpfile_path}"'
    )
    b64 = base64.b64encode((relay + "\n").encode()).decode()
    cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | {Q_BINARY} -q"]
    result = container.exec_run(cmd, demux=True)
    stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
    stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
    return {"stdout": stdout, "stderr": stderr, "exit_code": result.exit_code}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_docker_manager.py -v
```

Expected: all 34 tests PASS

- [ ] **Step 5: Commit**

```bash
git add q_solver/mcp/docker_manager.py tests/test_docker_manager.py
git commit -m "feat: add session process functions to docker_manager"
```

---

## Task 2: Create session_manager.py

**Files:**
- Create: `q_solver/mcp/session_manager.py`
- Create: `tests/test_session_manager.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_session_manager.py`:

```python
import time
import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def fresh_manager(monkeypatch):
    import session_manager
    monkeypatch.setattr(session_manager, "_manager", None)
    monkeypatch.setattr("docker_manager.ensure_container_running", lambda: None)
    monkeypatch.setattr("docker_manager.get_client", lambda: MagicMock())
    mock_container = MagicMock()
    monkeypatch.setattr("docker_manager.get_container", lambda c: mock_container)
    monkeypatch.setattr("docker_manager.start_session_process", lambda c, p: None)
    monkeypatch.setattr("docker_manager.kill_session_process", lambda c, p: None)
    monkeypatch.setattr(
        "docker_manager.run_q_in_session_port",
        lambda c, p, sid, code: {"stdout": "ok\n", "stderr": "", "exit_code": 0},
    )
    yield mock_container


def test_create_session_allocates_port():
    from session_manager import get_manager
    result = get_manager().create_session()
    assert "session_id" in result
    assert 5001 <= result["port"] <= 5099


def test_create_session_with_group():
    from session_manager import get_manager
    result = get_manager().create_session(group="trading")
    assert result["group"] == "trading"


def test_run_in_session_updates_last_activity():
    from session_manager import get_manager
    mgr = get_manager()
    r = mgr.create_session()
    sid = r["session_id"]
    before = mgr._sessions[sid].last_activity
    time.sleep(0.05)
    mgr.run_in_session(sid, "1+1")
    assert mgr._sessions[sid].last_activity > before


def test_expire_session_kills_process(monkeypatch):
    killed = []
    monkeypatch.setattr("docker_manager.kill_session_process", lambda c, p: killed.append(p))
    from session_manager import get_manager
    mgr = get_manager()
    r = mgr.create_session()
    sid = r["session_id"]
    port = r["port"]
    mgr.expire_session(sid)
    assert port in killed
    assert mgr._sessions[sid].status == "expired"


def test_list_sessions_returns_all():
    from session_manager import get_manager
    mgr = get_manager()
    r1 = mgr.create_session(group="a")
    r2 = mgr.create_session(group="b")
    sessions = mgr.list_sessions()
    ids = [s["session_id"] for s in sessions]
    assert r1["session_id"] in ids
    assert r2["session_id"] in ids


def test_expired_session_resurrects_on_run():
    from session_manager import get_manager
    mgr = get_manager()
    r = mgr.create_session()
    sid = r["session_id"]
    mgr.expire_session(sid)
    assert mgr._sessions[sid].status == "expired"
    result = mgr.run_in_session(sid, "1+1")
    assert result["was_restarted"] is True
    assert mgr._sessions[sid].status == "running"


def test_session_limit_raises():
    from session_manager import get_manager, PORT_MIN, PORT_MAX
    mgr = get_manager()
    for _ in range(PORT_MAX - PORT_MIN + 1):
        mgr.create_session()
    with pytest.raises(RuntimeError, match="session limit reached"):
        mgr.create_session()


def test_unknown_session_id_raises():
    from session_manager import get_manager
    with pytest.raises(RuntimeError, match="session not found"):
        get_manager().run_in_session("nonexistent-id", "1+1")


def test_background_thread_expires_idle():
    from session_manager import get_manager
    mgr = get_manager()
    r = mgr.create_session()
    sid = r["session_id"]
    mgr._sessions[sid].last_activity = time.time() - 700
    mgr._expire_idle_sessions()
    assert mgr._sessions[sid].status == "expired"
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_session_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'session_manager'`

- [ ] **Step 3: Implement session_manager.py**

Create `q_solver/mcp/session_manager.py`:

```python
import threading
import time
import uuid
from dataclasses import dataclass

import docker_manager

PORT_MIN = 5001
PORT_MAX = 5099
SESSION_TIMEOUT = 600


@dataclass
class QSession:
    session_id: str
    group: str | None
    port: int
    created_at: float
    last_activity: float
    status: str  # "running" | "expired"


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, QSession] = {}
        self._lock = threading.Lock()
        t = threading.Thread(target=self._expiry_loop, daemon=True)
        t.start()

    def _expiry_loop(self):
        while True:
            time.sleep(60)
            self._expire_idle_sessions()

    def _expire_idle_sessions(self):
        now = time.time()
        with self._lock:
            for session in self._sessions.values():
                if session.status == "running" and (now - session.last_activity) > SESSION_TIMEOUT:
                    self._kill_session(session)

    def _kill_session(self, session: QSession):
        try:
            client = docker_manager.get_client()
            container = docker_manager.get_container(client)
            if container:
                docker_manager.kill_session_process(container, session.port)
        except Exception:
            pass
        session.status = "expired"

    def _allocate_port(self) -> int:
        used = {s.port for s in self._sessions.values() if s.status == "running"}
        for port in range(PORT_MIN, PORT_MAX + 1):
            if port not in used:
                return port
        raise RuntimeError("session limit reached (100)")

    def _ensure_running(self, session: QSession) -> bool:
        if session.status == "running":
            return False
        client = docker_manager.get_client()
        container = docker_manager.get_container(client)
        docker_manager.start_session_process(container, session.port)
        now = time.time()
        session.created_at = now
        session.last_activity = now
        session.status = "running"
        return True

    def create_session(self, group: str | None = None) -> dict:
        docker_manager.ensure_container_running()
        with self._lock:
            port = self._allocate_port()
            session_id = str(uuid.uuid4())
            now = time.time()
            session = QSession(
                session_id=session_id,
                group=group,
                port=port,
                created_at=now,
                last_activity=now,
                status="running",
            )
            self._sessions[session_id] = session

        client = docker_manager.get_client()
        container = docker_manager.get_container(client)
        docker_manager.start_session_process(container, port)
        return {"session_id": session_id, "group": group, "port": port, "created_at": now}

    def run_in_session(self, session_id: str, code: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise RuntimeError(f"session not found: {session_id}")
            was_restarted = self._ensure_running(session)

        client = docker_manager.get_client()
        container = docker_manager.get_container(client)
        result = docker_manager.run_q_in_session_port(container, session.port, session_id, code)

        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].last_activity = time.time()

        return {**result, "was_restarted": was_restarted}

    def expire_session(self, session_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise RuntimeError(f"session not found: {session_id}")
            self._kill_session(session)
        return {"ok": True}

    def list_sessions(self) -> list:
        now = time.time()
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "group": s.group,
                    "status": s.status,
                    "idle_seconds": int(now - s.last_activity),
                    "created_at": s.created_at,
                }
                for s in self._sessions.values()
            ]


_manager: SessionManager | None = None
_manager_lock = threading.Lock()


def get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SessionManager()
    return _manager
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_session_manager.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Run full suite to check nothing broken**

```bash
python -m pytest tests/ -v
```

Expected: all 40 tests PASS

- [ ] **Step 6: Commit**

```bash
git add q_solver/mcp/session_manager.py tests/test_session_manager.py
git commit -m "feat: add SessionManager with persistent q session lifecycle"
```

---

## Task 3: Wire 4 new MCP tools in server.py

**Files:**
- Modify: `q_solver/mcp/server.py`

- [ ] **Step 1: Add import and 4 tools**

Edit `q_solver/mcp/server.py` — add after the existing imports:

```python
from session_manager import get_manager
```

Then add after the existing `get_logs` tool:

```python
@mcp.tool()
def create_session(group: str = None) -> dict:
    """
    Create a persistent q session. Returns {session_id, group, port, created_at}.
    Pass session_id to run_q_in_session to execute code with preserved state.
    Optionally tag with a group name to identify shared-context sessions.
    """
    return get_manager().create_session(group)


@mcp.tool()
def run_q_in_session(session_id: str, code: str) -> dict:
    """
    Run q/kdb+ code in a persistent session. Variables, functions, and tables
    defined in previous calls are available. Returns {stdout, stderr, exit_code, was_restarted}.
    was_restarted=True means the session expired and state was reset — inform the user.
    """
    return get_manager().run_in_session(session_id, code)


@mcp.tool()
def expire_session(session_id: str) -> dict:
    """
    Immediately kill a persistent q session's process. The session_id stays valid
    and will auto-resurrect with fresh state on the next run_q_in_session call.
    Returns {ok: true}.
    """
    return get_manager().expire_session(session_id)


@mcp.tool()
def list_sessions() -> list:
    """
    List all q sessions (running and expired) with group, status, and idle_seconds.
    """
    return get_manager().list_sessions()
```

- [ ] **Step 2: Verify server imports cleanly**

```bash
python -c "import sys; sys.path.insert(0, 'q_solver/mcp'); import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all 40 tests PASS

- [ ] **Step 4: Commit**

```bash
git add q_solver/mcp/server.py
git commit -m "feat: expose persistent session MCP tools (create/run/expire/list)"
```

---

## Task 4: Manual smoke test

- [ ] **Step 1: Restart Claude Code** so new MCP tools load

- [ ] **Step 2: Create a session and verify state persists**

Call `create_session()` → get `session_id`

Call `run_q_in_session(session_id, "x:42")` → defines `x` in session

Call `run_q_in_session(session_id, "x")` → should return `42`

- [ ] **Step 3: Verify expiry and resurrection**

Call `expire_session(session_id)`

Call `run_q_in_session(session_id, "x")` → `was_restarted: true`, `x` undefined (error expected)

- [ ] **Step 4: Verify throwaway run_q still works**

Call `run_q("1+1")` → `2`, no session involved

- [ ] **Step 5: Final commit if any fixes needed, then push**

```bash
git push
```
