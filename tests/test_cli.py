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


def test_register_mcp_writes_to_settings(tmp_path, monkeypatch):
    from q_solver.__main__ import _register_mcp, _CLAUDE_SETTINGS, _MCP_SERVER_NAME
    import q_solver.__main__ as cli
    settings_path = tmp_path / ".claude" / "settings.json"
    monkeypatch.setattr = lambda *a, **kw: None  # noqa — use direct attribute patch
    cli._CLAUDE_SETTINGS = settings_path
    _orig = cli._CLAUDE_SETTINGS
    cli._CLAUDE_SETTINGS = settings_path
    settings_path.parent.mkdir(parents=True)
    cli._register_mcp()
    data = json.loads(settings_path.read_text())
    assert _MCP_SERVER_NAME in data["mcpServers"]
    cli._CLAUDE_SETTINGS = _orig


def test_register_mcp_preserves_existing_settings(tmp_path):
    import q_solver.__main__ as cli
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"hooks": {"PreToolUse": []}}))
    cli._CLAUDE_SETTINGS = settings_path
    cli._register_mcp()
    data = json.loads(settings_path.read_text())
    assert "hooks" in data
    assert cli._MCP_SERVER_NAME in data["mcpServers"]


def test_unregister_mcp_removes_server(tmp_path):
    import q_solver.__main__ as cli
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "mcpServers": {"q-solver": {"command": "python", "args": []}}
    }))
    cli._CLAUDE_SETTINGS = settings_path
    cli._unregister_mcp()
    data = json.loads(settings_path.read_text())
    assert "q-solver" not in data.get("mcpServers", {})


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
