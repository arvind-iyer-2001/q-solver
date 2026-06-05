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


def test_register_mcp_calls_claude_mcp_add(monkeypatch):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    completed.stderr = ""
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or completed)
    cli._register_mcp()
    assert any("mcp" in str(c) and "add" in str(c) for c in calls)
    assert any(cli._MCP_SERVER_NAME in str(c) for c in calls)


def test_register_mcp_warns_on_failure(monkeypatch, capsys):
    import subprocess
    import q_solver.__main__ as cli
    failed = MagicMock()
    failed.returncode = 1
    failed.stderr = "claude not found"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: failed)
    cli._register_mcp()
    out = capsys.readouterr()
    assert "warning" in out.err or "manually" in out.err


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
