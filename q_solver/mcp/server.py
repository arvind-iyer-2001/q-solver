import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
import docker_manager

mcp = FastMCP("q-solver")


@mcp.tool()
def run_q(code: str) -> dict:
    """
    Execute q/kdb+ code in the persistent q-solver container.
    Returns dict with keys: stdout (str), stderr (str), exit_code (int).
    If the container is not initialized, raises RuntimeError with instructions.
    """
    return docker_manager.run_q(code)


@mcp.tool()
def get_container_status() -> dict:
    """
    Check if the q-solver Docker container is running.
    Returns dict with key: running (bool).
    """
    return docker_manager.get_container_status()


@mcp.tool()
def reset_session() -> bool:
    """Restart the q-solver container for a clean q state."""
    return docker_manager.reset_session()


@mcp.tool()
def get_logs(lines: int = 50) -> str:
    """Get the last N lines of q-solver container logs."""
    return docker_manager.get_logs(lines)


if __name__ == "__main__":
    mcp.run()
