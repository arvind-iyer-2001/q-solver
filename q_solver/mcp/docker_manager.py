import base64
import io
import subprocess
import tarfile
from pathlib import Path
import docker
import docker.errors
from credential_store import delete_config, get_license, KX_INSTALL_URL

BASE_IMAGE = "qtpy6969/kdb-x-runner:latest"
_DOCKERFILE_DIR = Path(__file__).parent.parent / "docker"
CONTAINER_NAME = "kdb-x-runner"
Q_BINARY = "/root/.kx/bin/q"
LICENSE_EXPIRY_SIGNALS = ["'licexp", "license expired"]


def get_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except docker.errors.DockerException as e:
        raise RuntimeError(
            f"Docker not available: {e}\n"
            "Install Docker: https://docs.docker.com/get-docker/"
        )


def image_exists(client: docker.DockerClient) -> bool:
    try:
        client.images.get(BASE_IMAGE)
        return True
    except docker.errors.ImageNotFound:
        return False


def get_container(client: docker.DockerClient):
    try:
        return client.containers.get(CONTAINER_NAME)
    except docker.errors.NotFound:
        return None


def pull_base_image(client: docker.DockerClient) -> None:
    client.images.pull(BASE_IMAGE)


def build_and_push_multiarch(license_key: str, tag: str = BASE_IMAGE) -> None:
    """Build a multi-arch image (linux/amd64 + linux/arm64) and push to Docker Hub.
    Requires: docker login, docker buildx with a multi-arch builder active."""
    result = subprocess.run(
        ["docker", "buildx", "create", "--use", "--name", "q-solver-builder"],
        capture_output=True, text=True,
    )
    # ignore error if builder already exists
    subprocess.run(
        [
            "docker", "buildx", "build",
            "--platform", "linux/amd64,linux/arm64",
            "--build-arg", f"B64LIC={license_key}",
            "-t", tag,
            "--push",
            str(_DOCKERFILE_DIR),
        ],
        check=True,
    )


def inject_license(container, license_key: str) -> None:
    lic_bytes = base64.b64decode(license_key)
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        info = tarfile.TarInfo(name='kc.lic')
        info.size = len(lic_bytes)
        tar.addfile(info, io.BytesIO(lic_bytes))
    tar_stream.seek(0)
    container.put_archive('/root/.kx/', tar_stream)


def _start_container(client: docker.DockerClient):
    return client.containers.run(
        BASE_IMAGE,
        name=CONTAINER_NAME,
        command="tail -f /dev/null",
        detach=True,
        restart_policy={"Name": "unless-stopped"},
    )


def setup_container(license_key: str) -> None:
    client = get_client()
    pull_base_image(client)
    existing = get_container(client)
    if existing:
        existing.stop()
        existing.remove()
    container = _start_container(client)
    inject_license(container, license_key)


def ensure_container_running() -> None:
    client = get_client()
    if not image_exists(client):
        raise RuntimeError(
            "Q Solver not initialized. Run 'q-solver install' to set up.\n"
            f"Get your license at: {KX_INSTALL_URL}"
        )
    container = get_container(client)
    if container is None:
        license_key = get_license()
        if not license_key:
            raise RuntimeError(
                "Q Solver not initialized. Run 'q-solver install' to set up.\n"
                f"Get your license at: {KX_INSTALL_URL}"
            )
        container = _start_container(client)
        inject_license(container, license_key)
    elif container.status != "running":
        container.start()


def _is_license_expired(text: str) -> bool:
    lower = text.lower()
    return any(signal.lower() in lower for signal in LICENSE_EXPIRY_SIGNALS)


def _handle_license_expiry() -> None:
    client = get_client()
    container = get_container(client)
    if container:
        container.stop()
        container.remove()
    delete_config()
    raise RuntimeError(
        "KX license has expired. Run 'q-solver install' to re-enter your license.\n"
        f"Get a new license at: {KX_INSTALL_URL}"
    )


def run_q(code: str) -> dict:
    ensure_container_running()
    client = get_client()
    container = get_container(client)

    b64 = base64.b64encode((code + "\n").encode()).decode()
    cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | {Q_BINARY} -q"]

    result = container.exec_run(cmd, demux=True)
    stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
    stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
    exit_code = result.exit_code

    if _is_license_expired(stderr) or _is_license_expired(stdout):
        _handle_license_expiry()
        result = container.exec_run(cmd, demux=True)
        stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
        stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
        exit_code = result.exit_code

    return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}


def get_container_status() -> dict:
    client = get_client()
    container = get_container(client)
    if container is None:
        return {"running": False}
    container.reload()
    return {"running": container.status == "running"}


def reset_session() -> bool:
    client = get_client()
    container = get_container(client)
    if container:
        container.restart()
    return True


def get_logs(lines: int = 50) -> str:
    client = get_client()
    container = get_container(client)
    if container is None:
        return ""
    return container.logs(tail=lines).decode("utf-8", errors="replace")
