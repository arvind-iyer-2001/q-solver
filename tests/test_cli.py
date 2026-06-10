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


def test_uninstall_skills_keeps_nonempty_parent_dir(tmp_path, monkeypatch):
    import q_solver.__main__ as cli
    dst_root = tmp_path / ".claude" / "skills"
    for name in cli._SKILL_NAMES:
        (dst_root / name).mkdir(parents=True)
        (dst_root / name / "SKILL.md").write_text(f"# {name}")
        (dst_root / name / "extra.txt").write_text("keep me")
    monkeypatch.setattr(cli, "_SKILLS_DST_ROOT", dst_root)
    cli._uninstall_skills()
    for name in cli._SKILL_NAMES:
        assert not (dst_root / name / "SKILL.md").exists()
        assert (dst_root / name / "extra.txt").exists()


def test_mcp_registered_false_on_nonzero_returncode(monkeypatch):
    import subprocess
    import q_solver.__main__ as cli
    failed = MagicMock()
    failed.returncode = 1
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: failed)
    assert cli._mcp_registered() is False


def test_verify_mcp_warns_on_nonzero_returncode(monkeypatch, capsys):
    import subprocess
    import q_solver.__main__ as cli
    failed = MagicMock()
    failed.returncode = 1
    failed.stderr = "claude not found"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: failed)
    cli._verify_mcp()
    out = capsys.readouterr()
    assert "could not verify MCP" in out.err


def test_verify_mcp_reports_connected(monkeypatch, capsys):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = f"{cli._MCP_SERVER_NAME}: docker run ... - ✔ Connected\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    cli._verify_mcp()
    out = capsys.readouterr()
    assert "MCP verified    -> connected" in out.out


def test_verify_mcp_reports_raw_status_when_not_connected(monkeypatch, capsys):
    import subprocess
    import q_solver.__main__ as cli
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = f"{cli._MCP_SERVER_NAME}: docker run ... - ✗ Failed\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    cli._verify_mcp()
    out = capsys.readouterr()
    assert "MCP status" in out.out


def test_cmd_install_empty_license_exits(monkeypatch, fake_home):
    import getpass
    import q_solver.__main__ as cli
    monkeypatch.setattr(getpass, "getpass", lambda prompt: "")
    with pytest.raises(SystemExit) as exc:
        cli.cmd_install([])
    assert exc.value.code == 1


def test_cmd_install_full_flow_without_build(monkeypatch, fake_home, capsys):
    import getpass
    import q_solver.__main__ as cli
    import credential_store, docker_manager

    monkeypatch.setattr(getpass, "getpass", lambda prompt: "bGljZW5zZQ==")
    monkeypatch.setattr(credential_store, "setup_with_license", lambda key: None)
    monkeypatch.setattr(cli, "_install_skills", lambda: None)
    monkeypatch.setattr(cli, "_register_mcp", lambda: None)
    monkeypatch.setattr(docker_manager, "get_client", lambda: MagicMock())
    monkeypatch.setattr(docker_manager, "pull_mcp_image", lambda client: None)
    setup_calls = []
    monkeypatch.setattr(docker_manager, "setup_container", lambda key: setup_calls.append(key))

    cli.cmd_install([])

    out = capsys.readouterr().out
    assert "license saved" in out
    assert f"pulled -> {docker_manager.MCP_IMAGE}" in out
    assert "To build the Docker image now" in out
    assert setup_calls == []


def test_cmd_install_with_build_flag(monkeypatch, fake_home, capsys):
    import getpass
    import q_solver.__main__ as cli
    import credential_store, docker_manager

    monkeypatch.setattr(getpass, "getpass", lambda prompt: "bGljZW5zZQ==")
    monkeypatch.setattr(credential_store, "setup_with_license", lambda key: None)
    monkeypatch.setattr(cli, "_install_skills", lambda: None)
    monkeypatch.setattr(cli, "_register_mcp", lambda: None)
    monkeypatch.setattr(docker_manager, "get_client", lambda: MagicMock())
    monkeypatch.setattr(docker_manager, "pull_mcp_image", lambda client: None)
    setup_calls = []
    monkeypatch.setattr(docker_manager, "setup_container", lambda key: setup_calls.append(key))

    cli.cmd_install(["--build"])

    out = capsys.readouterr().out
    assert "container started -> kdb-x-runner" in out
    assert "To build the Docker image now" not in out
    assert setup_calls == ["bGljZW5zZQ=="]


def test_cmd_install_pull_mcp_image_failure_warns(monkeypatch, fake_home, capsys):
    import getpass
    import q_solver.__main__ as cli
    import credential_store, docker_manager

    monkeypatch.setattr(getpass, "getpass", lambda prompt: "bGljZW5zZQ==")
    monkeypatch.setattr(credential_store, "setup_with_license", lambda key: None)
    monkeypatch.setattr(cli, "_install_skills", lambda: None)
    monkeypatch.setattr(cli, "_register_mcp", lambda: None)
    monkeypatch.setattr(docker_manager, "get_client", lambda: MagicMock())

    def boom(client):
        raise RuntimeError("pull failed")
    monkeypatch.setattr(docker_manager, "pull_mcp_image", boom)

    cli.cmd_install([])

    err = capsys.readouterr().err
    assert "warning: could not pull MCP image" in err


def test_cmd_build_no_license_exits(monkeypatch, fake_home):
    import credential_store
    import q_solver.__main__ as cli
    monkeypatch.setattr(credential_store, "get_license", lambda: None)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_build([])
    assert exc.value.code == 1


def test_cmd_build_with_license_calls_setup_container(monkeypatch, fake_home, capsys):
    import credential_store, docker_manager
    import q_solver.__main__ as cli
    monkeypatch.setattr(credential_store, "get_license", lambda: "bGljZW5zZQ==")
    calls = []
    monkeypatch.setattr(docker_manager, "setup_container", lambda key: calls.append(key))
    cli.cmd_build([])
    assert calls == ["bGljZW5zZQ=="]
    assert "Done. Container q-solver is running." in capsys.readouterr().out


def test_cmd_publish_default_tag(monkeypatch, capsys):
    import docker_manager
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(docker_manager, "build_and_push_multiarch", lambda tag: calls.append(tag))
    cli.cmd_publish([])
    assert calls == [docker_manager.BASE_IMAGE]
    assert f"Pushed: {docker_manager.BASE_IMAGE}" in capsys.readouterr().out


def test_cmd_publish_custom_tag(monkeypatch):
    import docker_manager
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(docker_manager, "build_and_push_multiarch", lambda tag: calls.append(tag))
    cli.cmd_publish(["--tag", "myrepo/img:v1"])
    assert calls == ["myrepo/img:v1"]


def test_cmd_publish_mcp_default_tag(monkeypatch, capsys):
    import docker_manager
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(docker_manager, "build_and_push_mcp_image", lambda tag: calls.append(tag))
    cli.cmd_publish_mcp([])
    assert calls == [docker_manager.MCP_IMAGE]
    assert f"Pushed: {docker_manager.MCP_IMAGE}" in capsys.readouterr().out


def test_cmd_publish_mcp_custom_tag(monkeypatch):
    import docker_manager
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(docker_manager, "build_and_push_mcp_image", lambda tag: calls.append(tag))
    cli.cmd_publish_mcp(["--tag", "myrepo/mcp:v2"])
    assert calls == ["myrepo/mcp:v2"]


def test_cmd_uninstall_calls_helpers(monkeypatch, capsys):
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(cli, "_uninstall_skills", lambda: calls.append("skills"))
    monkeypatch.setattr(cli, "_unregister_mcp", lambda: calls.append("mcp"))
    cli.cmd_uninstall([])
    assert calls == ["skills", "mcp"]
    assert "Done." in capsys.readouterr().out


def test_cmd_status_full_success(monkeypatch, fake_home, capsys):
    import subprocess
    import credential_store, docker_manager
    import q_solver.__main__ as cli

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = f"{cli._MCP_SERVER_NAME}: ... - ✔ Connected\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    monkeypatch.setattr(credential_store, "get_license", lambda: "lic")
    monkeypatch.setattr(docker_manager, "get_client", lambda: MagicMock())
    monkeypatch.setattr(docker_manager, "image_exists", lambda client, image: True)
    monkeypatch.setattr(docker_manager, "get_container_status", lambda: {"running": True})

    cli.cmd_status([])

    out = capsys.readouterr().out
    assert "MCP server:    registered" in out
    assert "license:       stored" in out
    assert "MCP image:     present" in out
    assert "container:     running" in out


def test_cmd_status_docker_unavailable(monkeypatch, fake_home, capsys):
    import subprocess
    import credential_store, docker_manager
    import q_solver.__main__ as cli

    completed = MagicMock()
    completed.returncode = 1
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: completed)
    monkeypatch.setattr(credential_store, "get_license", lambda: None)

    def boom():
        raise RuntimeError("Docker not available")
    monkeypatch.setattr(docker_manager, "get_client", boom)

    cli.cmd_status([])

    out = capsys.readouterr().out
    assert "MCP server:    not registered" in out
    assert "license:       not stored" in out
    assert "container:     error — Docker not available" in out


def test_main_no_args_prints_usage(monkeypatch, capsys):
    import q_solver.__main__ as cli
    monkeypatch.setattr(sys, "argv", ["q-solver"])
    cli.main()
    assert "Usage: q-solver <command>" in capsys.readouterr().out


def test_main_help_flag_prints_usage(monkeypatch, capsys):
    import q_solver.__main__ as cli
    monkeypatch.setattr(sys, "argv", ["q-solver", "--help"])
    cli.main()
    assert "Usage: q-solver <command>" in capsys.readouterr().out


def test_main_unknown_command_exits(monkeypatch):
    import q_solver.__main__ as cli
    monkeypatch.setattr(sys, "argv", ["q-solver", "bogus"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_main_dispatches_command_with_args(monkeypatch):
    import q_solver.__main__ as cli
    calls = []
    monkeypatch.setattr(cli, "cmd_status", lambda args: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["q-solver", "status", "extra"])
    cli.main()
    assert calls == [["extra"]]
