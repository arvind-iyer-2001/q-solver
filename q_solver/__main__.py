"""q-solver CLI — install skills, register MCP server, manage container."""
from __future__ import annotations
import getpass
import shutil
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).parent
_SKILLS_SRC = _PKG_DIR / "skills"
_SKILLS_DST_ROOT = Path.home() / ".claude" / "skills"
_MCP_SERVER_NAME = "q-solver"
_SKILL_NAMES = ["q-solve", "q-run", "q-debug"]

KX_INSTALL_URL = "https://developer.kx.com/products/kdb-x/install"


def _mcp_registered() -> bool:
    import subprocess
    result = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True, text=True,
        cwd=str(_PKG_DIR),
    )
    if result.returncode != 0:
        return False
    return any(_MCP_SERVER_NAME in line for line in result.stdout.splitlines())


def _mcp_docker_args() -> list[str]:
    sys.path.insert(0, str(_PKG_DIR / "mcp"))
    import docker_manager
    config_dir = str(Path.home() / ".config" / "q-solver")
    return [
        "run", "-i", "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{config_dir}:/root/.config/q-solver",
        docker_manager.MCP_IMAGE,
    ]


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
    import subprocess
    docker_args = _mcp_docker_args()
    result = subprocess.run(
        ["claude", "mcp", "add", _MCP_SERVER_NAME, "docker", "--", *docker_args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  warning: claude mcp add failed: {result.stderr.strip()}", file=sys.stderr)
        print(f"  run manually: claude mcp add {_MCP_SERVER_NAME} docker -- {' '.join(docker_args)}")
        return
    print("  MCP registered via claude mcp add (docker)")
    _verify_mcp()


def _verify_mcp() -> None:
    import subprocess
    result = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True, text=True,
        cwd=str(_PKG_DIR),
    )
    if result.returncode != 0:
        print(f"  could not verify MCP: {result.stderr.strip()}", file=sys.stderr)
        return
    for line in result.stdout.splitlines():
        if _MCP_SERVER_NAME in line:
            if "Connected" in line or "✓" in line:
                print("  MCP verified    -> connected")
            else:
                print(f"  MCP status      -> {line.strip()}")
            return
    print(f"  warning: {_MCP_SERVER_NAME} not found in 'claude mcp list'", file=sys.stderr)
    print("  restart Claude Code for changes to take effect")


def _unregister_mcp() -> None:
    import subprocess
    result = subprocess.run(
        ["claude", "mcp", "remove", _MCP_SERVER_NAME, "-s", "local"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  MCP removed via claude mcp remove")


def cmd_install(args: list[str]) -> None:
    build = "--build" in args

    print("Q Solver — install\n")
    print(f"Get your KX license key at: {KX_INSTALL_URL}\n")
    license_key = getpass.getpass("Enter LICENSE_KEY (base64): ").strip()
    if not license_key:
        print("error: license key is required", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(_PKG_DIR / "mcp"))
    import credential_store
    import docker_manager
    credential_store.setup_with_license(license_key)
    print(f"  license saved  -> {credential_store.CONFIG_PATH}")

    _install_skills()

    print("\nPulling MCP server image...")
    try:
        docker_manager.pull_mcp_image(docker_manager.get_client())
        print(f"  pulled -> {docker_manager.MCP_IMAGE}")
    except Exception as e:
        print(f"  warning: could not pull MCP image: {e}", file=sys.stderr)

    _register_mcp()

    if build:
        print("\nBuilding Docker image (this takes a few minutes)...")
        docker_manager.setup_container(license_key)
        print("  container started -> kdb-x-runner")

    print("\nDone. Restart Claude Code, then try:\n  /q-run 1+1")
    if not build:
        print("\nTo build the Docker image now:\n  q-solver build")


def cmd_build(args: list[str]) -> None:
    sys.path.insert(0, str(_PKG_DIR / "mcp"))
    import credential_store
    import docker_manager

    license_key = credential_store.get_license()
    if not license_key:
        print("error: no license key stored. Run 'q-solver install' first.", file=sys.stderr)
        sys.exit(1)

    print("Building Docker image (this takes a few minutes)...")
    docker_manager.setup_container(license_key)
    print("Done. Container q-solver is running.")


def cmd_publish(args: list[str]) -> None:
    tag = None
    for i, a in enumerate(args):
        if a == "--tag" and i + 1 < len(args):
            tag = args[i + 1]

    sys.path.insert(0, str(_PKG_DIR / "mcp"))
    import docker_manager

    target = tag or docker_manager.BASE_IMAGE
    print(f"Building multi-arch image ({target}) for linux/amd64 + linux/arm64...")
    print("Requires: docker login, docker buildx.\n")
    docker_manager.build_and_push_multiarch(tag=target)
    print(f"\nPushed: {target}")


def cmd_publish_mcp(args: list[str]) -> None:
    tag = None
    for i, a in enumerate(args):
        if a == "--tag" and i + 1 < len(args):
            tag = args[i + 1]

    sys.path.insert(0, str(_PKG_DIR / "mcp"))
    import docker_manager

    target = tag or docker_manager.MCP_IMAGE
    print(f"Building multi-arch MCP server image ({target}) for linux/amd64 + linux/arm64...")
    print("Requires: docker login, docker buildx.\n")
    docker_manager.build_and_push_mcp_image(tag=target)
    print(f"\nPushed: {target}")


def cmd_uninstall(args: list[str]) -> None:
    _uninstall_skills()
    _unregister_mcp()
    print("\nDone.")


def cmd_status(args: list[str]) -> None:
    sys.path.insert(0, str(_PKG_DIR / "mcp"))

    for name in _SKILL_NAMES:
        dst = _SKILLS_DST_ROOT / name / "SKILL.md"
        state = "installed" if dst.exists() else "not installed"
        print(f"  skill {name}: {state}")

    mcp_state = "registered" if _mcp_registered() else "not registered"
    print(f"  MCP server:    {mcp_state}")

    import credential_store
    lic = credential_store.get_license()
    print(f"  license:       {'stored' if lic else 'not stored'}")

    try:
        import docker_manager
        client = docker_manager.get_client()
        mcp_image = "present" if docker_manager.image_exists(client, docker_manager.MCP_IMAGE) else "not pulled"
        print(f"  MCP image:     {mcp_image}")
        status = docker_manager.get_container_status()
        print(f"  container:     {'running' if status['running'] else 'stopped'}")
    except RuntimeError as e:
        print(f"  container:     error — {e}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: q-solver <command>")
        print()
        print("Commands:")
        print("  install [--build]        install skills + MCP, prompt for license key")
        print("  build                    build Docker image using stored license key")
        print("  publish [--tag TAG]      build + push multi-arch kdb-x-runner image to Docker Hub")
        print("  publish-mcp [--tag TAG]  build + push multi-arch q-solver-mcp image to Docker Hub")
        print("  uninstall                remove skills and MCP registration")
        print("  status                   show install status")
        return

    cmd = sys.argv[1]
    rest = sys.argv[2:]
    dispatch = {
        "install": cmd_install,
        "build": cmd_build,
        "publish": cmd_publish,
        "publish-mcp": cmd_publish_mcp,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
    }
    if cmd not in dispatch:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        sys.exit(1)
    dispatch[cmd](rest)


if __name__ == "__main__":
    main()
