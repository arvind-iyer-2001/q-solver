import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_mcp_docker_args_mounts_socket_and_config(fake_home):
    import q_solver.__main__ as cli
    import docker_manager
    args = cli._mcp_docker_args()
    assert args[0] == "run"
    assert "/var/run/docker.sock:/var/run/docker.sock" in args
    assert f"{fake_home / '.config' / 'q-solver'}:/root/.config/q-solver" in args
    assert args[-1] == docker_manager.MCP_IMAGE


def test_register_mcp_calls_claude_mcp_add(monkeypatch, fake_home):
    import subprocess
    import q_solver.__main__ as cli
    import docker_manager
    completed = MagicMock()
    completed.returncode = 0
    completed.stderr = ""
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or completed)
    cli._register_mcp()
    add_calls = [c for c in calls if "add" in c]
    assert add_calls, "expected a 'claude mcp add' call"
    add_cmd = add_calls[0]
    assert add_cmd[:4] == ["claude", "mcp", "add", cli._MCP_SERVER_NAME]
    assert add_cmd[4] == "docker"
    assert "run" in add_cmd
    assert "/var/run/docker.sock:/var/run/docker.sock" in add_cmd
    assert docker_manager.MCP_IMAGE in add_cmd


def test_register_mcp_warns_on_failure(monkeypatch, capsys, fake_home):
    import subprocess
    import q_solver.__main__ as cli
    failed = MagicMock()
    failed.returncode = 1
    failed.stderr = "claude not found"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: failed)
    cli._register_mcp()
    out = capsys.readouterr()
    assert "warning" in out.err or "manually" in out.err
    assert "docker" in out.out


def test_mcp_registered_true_when_in_claude_mcp_list(monkeypatch):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = "q-solver: docker run ... - ✔ Connected\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    assert cli._mcp_registered() is True


def test_mcp_registered_false_when_absent(monkeypatch):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = "some-other-server: ... - ✔ Connected\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    assert cli._mcp_registered() is False


def test_unregister_mcp_calls_claude_mcp_remove(monkeypatch):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or completed)
    cli._unregister_mcp()
    assert any("remove" in str(c) for c in calls)
    assert any(cli._MCP_SERVER_NAME in str(c) for c in calls)


def test_install_skills_copies_files(tmp_path, monkeypatch):
    import q_solver.__main__ as cli
    src_root = tmp_path / "skills"
    dst_root = tmp_path / ".claude" / "skills"
    for name in cli._SKILL_NAMES:
        (src_root / name).mkdir(parents=True)
        (src_root / name / "SKILL.md").write_text(f"# {name}")
    monkeypatch.setattr(cli, "_SKILLS_SRC", src_root)
    monkeypatch.setattr(cli, "_SKILLS_DST_ROOT", dst_root)
    cli._install_skills()
    for name in cli._SKILL_NAMES:
        assert (dst_root / name / "SKILL.md").exists()


def test_uninstall_skills_removes_files(tmp_path, monkeypatch):
    import q_solver.__main__ as cli
    dst_root = tmp_path / ".claude" / "skills"
    for name in cli._SKILL_NAMES:
        (dst_root / name).mkdir(parents=True)
        (dst_root / name / "SKILL.md").write_text(f"# {name}")
    monkeypatch.setattr(cli, "_SKILLS_DST_ROOT", dst_root)
    cli._uninstall_skills()
    for name in cli._SKILL_NAMES:
        assert not (dst_root / name / "SKILL.md").exists()
