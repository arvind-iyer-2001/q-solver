"""q-solver CLI — install skills, register MCP server, manage container."""
from __future__ import annotations
import getpass
import json
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SKILLS_SRC = _REPO_ROOT / "skills"
_SKILLS_DST_ROOT = Path.home() / ".claude" / "skills"
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
_MCP_SERVER_NAME = "q-solver"
_SKILL_NAMES = ["q-solve", "q-run", "q-debug"]

KX_INSTALL_URL = "https://developer.kx.com/products/kdb-x/install"


def _read_settings() -> dict:
    if _CLAUDE_SETTINGS.exists():
        try:
            return json.loads(_CLAUDE_SETTINGS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _write_settings(settings: dict) -> None:
    _CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    _CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _mcp_server_path() -> str:
    return str(_REPO_ROOT / "mcp" / "server.py")


def _install_skills() -> None:
    for name in _SKILL_NAMES:
        src = _SKILLS_SRC / name / "SKILL.md"
        dst = _SKILLS_DST_ROOT / name / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        print(f"  skill installed -> {dst}")


def _uninstall_skills() -> None:
    for name in _SKILL_NAMES:
        dst = _SKILLS_DST_ROOT / name / "SKILL.md"
        if dst.exists():
            dst.unlink()
            try:
                dst.parent.rmdir()
            except OSError:
                pass
            print(f"  skill removed  -> {dst}")


def _register_mcp() -> None:
    settings = _read_settings()
    mcp_servers = settings.setdefault("mcpServers", {})
    mcp_servers[_MCP_SERVER_NAME] = {
        "command": sys.executable,
        "args": [_mcp_server_path()],
        "env": {},
    }
    _write_settings(settings)
    print(f"  MCP registered -> {_CLAUDE_SETTINGS}")


def _unregister_mcp() -> None:
    settings = _read_settings()
    if _MCP_SERVER_NAME in settings.get("mcpServers", {}):
        del settings["mcpServers"][_MCP_SERVER_NAME]
        _write_settings(settings)
        print(f"  MCP removed    -> {_CLAUDE_SETTINGS}")


def cmd_install(args: list[str]) -> None:
    build = "--build" in args

    print("Q Solver — install\n")
    print(f"Get your KX license key at: {KX_INSTALL_URL}\n")
    license_key = getpass.getpass("Enter LICENSE_KEY (base64): ").strip()
    if not license_key:
        print("error: license key is required", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(_REPO_ROOT / "mcp"))
    import credential_store
    credential_store.setup_with_license(license_key)
    print(f"  license saved  -> {credential_store.CONFIG_PATH}")

    _install_skills()
    _register_mcp()

    if build:
        print("\nBuilding Docker image (this takes a few minutes)...")
        import docker_manager
        docker_manager.setup_container(license_key)
        print("  container started -> q-solver")

    print("\nDone. Restart Claude Code, then try:\n  /q-run 1+1")
    if not build:
        print("\nTo build the Docker image now:\n  q-solver build")


def cmd_build(args: list[str]) -> None:
    sys.path.insert(0, str(_REPO_ROOT / "mcp"))
    import credential_store, docker_manager

    license_key = credential_store.get_license()
    if not license_key:
        print("error: no license key stored. Run 'q-solver install' first.", file=sys.stderr)
        sys.exit(1)

    print("Building Docker image (this takes a few minutes)...")
    docker_manager.setup_container(license_key)
    print("Done. Container q-solver is running.")


def cmd_uninstall(args: list[str]) -> None:
    _uninstall_skills()
    _unregister_mcp()
    print("\nDone.")


def cmd_status(args: list[str]) -> None:
    sys.path.insert(0, str(_REPO_ROOT / "mcp"))

    for name in _SKILL_NAMES:
        dst = _SKILLS_DST_ROOT / name / "SKILL.md"
        state = "installed" if dst.exists() else "not installed"
        print(f"  skill {name}: {state}")

    settings = _read_settings()
    mcp_state = "registered" if _MCP_SERVER_NAME in settings.get("mcpServers", {}) else "not registered"
    print(f"  MCP server:    {mcp_state}")

    import credential_store
    lic = credential_store.get_license()
    print(f"  license:       {'stored' if lic else 'not stored'}")

    try:
        import docker_manager
        status = docker_manager.get_container_status()
        print(f"  container:     {'running' if status['running'] else 'stopped'}")
    except RuntimeError as e:
        print(f"  container:     error — {e}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: q-solver <command>")
        print()
        print("Commands:")
        print("  install [--build]  install skills + MCP, prompt for license key")
        print("  build              build Docker image using stored license key")
        print("  uninstall          remove skills and MCP registration")
        print("  status             show install status")
        return

    cmd = sys.argv[1]
    rest = sys.argv[2:]
    dispatch = {
        "install": cmd_install,
        "build": cmd_build,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
    }
    if cmd not in dispatch:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        sys.exit(1)
    dispatch[cmd](rest)


if __name__ == "__main__":
    main()
