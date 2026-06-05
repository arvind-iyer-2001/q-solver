import base64
import io
import docker
import docker.errors
from credential_store import delete_config, KX_INSTALL_URL

IMAGE_NAME = "q-solver:latest"
CONTAINER_NAME = "q-solver"
Q_BINARY = "/root/.kx/bin/q"
LICENSE_EXPIRY_SIGNALS = ["'licexp", "license expired"]

DOCKERFILE_TEMPLATE = (
    "FROM ubuntu:22.04\n"
    "ENV DEBIAN_FRONTEND=noninteractive\n"
    "ENV TERM=xterm\n"
    "RUN apt-get update && apt-get install -y curl unzip ncurses-bin && "
    "curl -sLO https://portal.dl.kx.com/assets/raw/kdb-x/install_kdb/~latest~/install_kdb.sh && "
    "bash install_kdb.sh -y --b64lic '{license_key}'\n"
)


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
        client.images.get(IMAGE_NAME)
        return True
    except docker.errors.ImageNotFound:
        return False


def get_container(client: docker.DockerClient):
    try:
        return client.containers.get(CONTAINER_NAME)
    except docker.errors.NotFound:
        return None


def build_image(license_key: str) -> None:
    client = get_client()
    dockerfile = DOCKERFILE_TEMPLATE.format(license_key=license_key)
    fileobj = io.BytesIO(dockerfile.encode())
    try:
        client.images.build(fileobj=fileobj, tag=IMAGE_NAME, rm=True)
    except docker.errors.BuildError as e:
        build_log = "\n".join(
            line.get("stream", "") for line in e.build_log if "stream" in line
        )
        raise RuntimeError(f"Image build failed:\n{build_log}")


def setup_container(license_key: str) -> None:
    build_image(license_key)
    client = get_client()
    existing = get_container(client)
    if existing:
        existing.stop()
        existing.remove()
    client.containers.run(
        IMAGE_NAME,
        name=CONTAINER_NAME,
        command="tail -f /dev/null",
        detach=True,
        restart_policy={"Name": "unless-stopped"},
    )


def ensure_container_running() -> None:
    client = get_client()
    if not image_exists(client):
        raise RuntimeError(
            "Q Solver not initialized. Run 'q-solver install' to set up.\n"
            f"Get your license at: {KX_INSTALL_URL}"
        )
    container = get_container(client)
    if container is None:
        client.containers.run(
            IMAGE_NAME,
            name=CONTAINER_NAME,
            command="tail -f /dev/null",
            detach=True,
            restart_policy={"Name": "unless-stopped"},
        )
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
    try:
        client.images.remove(IMAGE_NAME, force=True)
    except docker.errors.ImageNotFound:
        pass
    delete_config()
    raise RuntimeError(
        "KX license has expired. Run 'q-solver install' to re-enter your license.\n"
        f"Get a new license at: {KX_INSTALL_URL}"
    )


def run_q(code: str) -> dict:
    ensure_container_running()
    client = get_client()
    container = get_container(client)

    b64 = base64.b64encode(code.encode()).decode()
    cmd = ["bash", "-c", f"base64 -d <<< '{b64}' | {Q_BINARY} -q"]

    result = container.exec_run(cmd, demux=True)
    stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
    stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
    exit_code = result.exit_code

    if _is_license_expired(stderr) or _is_license_expired(stdout):
        _handle_license_expiry()
        # If _handle_license_expiry didn't raise (e.g. in tests), retry
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
