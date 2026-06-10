def test_run_q_delegates_to_docker_manager(monkeypatch):
    import server
    import docker_manager
    monkeypatch.setattr(docker_manager, "run_q", lambda code: {"stdout": code, "stderr": "", "exit_code": 0})
    assert server.run_q("1+1") == {"stdout": "1+1", "stderr": "", "exit_code": 0}


def test_get_container_status_delegates(monkeypatch):
    import server
    import docker_manager
    monkeypatch.setattr(docker_manager, "get_container_status", lambda: {"running": True})
    assert server.get_container_status() == {"running": True}


def test_reset_session_delegates(monkeypatch):
    import server
    import docker_manager
    monkeypatch.setattr(docker_manager, "reset_session", lambda: True)
    assert server.reset_session() is True


def test_get_logs_delegates(monkeypatch):
    import server
    import docker_manager
    monkeypatch.setattr(docker_manager, "get_logs", lambda lines=50: f"last {lines} lines")
    assert server.get_logs(10) == "last 10 lines"
