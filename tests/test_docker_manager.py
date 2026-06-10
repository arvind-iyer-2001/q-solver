import pytest
from unittest.mock import MagicMock, patch
import docker.errors


@pytest.fixture
def mock_client(monkeypatch):
    import docker_manager
    client = MagicMock()
    monkeypatch.setattr(docker_manager, "get_client", lambda: client)
    return client


def test_get_client_raises_when_docker_unavailable():
    import docker_manager
    with patch("docker.from_env", side_effect=docker.errors.DockerException("no docker")):
        with pytest.raises(RuntimeError, match="Docker not available"):
            docker_manager.get_client()


def test_image_exists_true(mock_client):
    import docker_manager
    mock_client.images.get.return_value = MagicMock()
    assert docker_manager.image_exists(mock_client) is True


def test_image_exists_false(mock_client):
    import docker_manager
    mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")
    assert docker_manager.image_exists(mock_client) is False


def test_image_exists_for_custom_image(mock_client):
    import docker_manager
    mock_client.images.get.return_value = MagicMock()
    assert docker_manager.image_exists(mock_client, docker_manager.MCP_IMAGE) is True
    mock_client.images.get.assert_called_with(docker_manager.MCP_IMAGE)


def test_pull_mcp_image_calls_images_pull(mock_client):
    import docker_manager
    docker_manager.pull_mcp_image(mock_client)
    mock_client.images.pull.assert_called_once_with(docker_manager.MCP_IMAGE)


def test_build_and_push_mcp_image_invokes_buildx(monkeypatch):
    import docker_manager
    import subprocess

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    docker_manager.build_and_push_mcp_image(tag="example/q-solver-mcp:test")

    build_cmd = calls[1]
    assert "buildx" in build_cmd
    assert "-f" in build_cmd
    assert str(docker_manager._DOCKERFILE_DIR / "Dockerfile.mcp") in build_cmd
    assert "example/q-solver-mcp:test" in build_cmd
    assert "--push" in build_cmd
    assert str(docker_manager._PKG_DIR) in build_cmd


def test_get_container_returns_container(mock_client):
    import docker_manager
    container = MagicMock()
    mock_client.containers.get.return_value = container
    assert docker_manager.get_container(mock_client) is container


def test_get_container_returns_none_when_not_found(mock_client):
    import docker_manager
    mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
    assert docker_manager.get_container(mock_client) is None


def test_is_license_expired_detects_licexp():
    import docker_manager
    assert docker_manager._is_license_expired("'licexp\n") is True


def test_is_license_expired_detects_license_expired():
    import docker_manager
    assert docker_manager._is_license_expired("license expired") is True


def test_is_license_expired_false_for_normal_output():
    import docker_manager
    assert docker_manager._is_license_expired("2\n") is False


def test_run_q_success(mock_client):
    import docker_manager
    container = MagicMock()
    container.status = "running"
    mock_client.containers.get.return_value = container
    mock_client.images.get.return_value = MagicMock()

    exec_result = MagicMock()
    exec_result.exit_code = 0
    exec_result.output = (b"2\n", b"")
    container.exec_run.return_value = exec_result

    result = docker_manager.run_q("1+1")

    assert result["exit_code"] == 0
    assert result["stdout"] == "2\n"
    assert result["stderr"] == ""


def test_run_q_raises_on_license_expiry(mock_client, monkeypatch):
    import docker_manager
    container = MagicMock()
    container.status = "running"
    mock_client.containers.get.return_value = container
    mock_client.images.get.return_value = MagicMock()

    expired = MagicMock()
    expired.exit_code = 1
    expired.output = (b"", b"'licexp\n")
    container.exec_run.return_value = expired

    monkeypatch.setattr(docker_manager, "delete_config", lambda: None)

    with pytest.raises(RuntimeError, match="license has expired"):
        docker_manager.run_q("1+1")

    container.stop.assert_called_once()
    container.remove.assert_called_once()


def test_get_container_status_running(mock_client):
    import docker_manager
    container = MagicMock()
    container.status = "running"
    mock_client.containers.get.return_value = container
    assert docker_manager.get_container_status() == {"running": True}


def test_get_container_status_not_found(mock_client):
    import docker_manager
    mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
    assert docker_manager.get_container_status() == {"running": False}


def test_get_logs_returns_empty_when_no_container(mock_client):
    import docker_manager
    mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
    assert docker_manager.get_logs(50) == ""


def test_get_logs_returns_decoded_output(mock_client):
    import docker_manager
    container = MagicMock()
    container.logs.return_value = b"q output here\n"
    mock_client.containers.get.return_value = container
    assert docker_manager.get_logs(10) == "q output here\n"


def test_reset_session_restarts_container(mock_client):
    import docker_manager
    container = MagicMock()
    mock_client.containers.get.return_value = container
    assert docker_manager.reset_session() is True
    container.restart.assert_called_once()


def test_ensure_container_running_raises_when_not_initialized(mock_client):
    import docker_manager
    mock_client.images.get.side_effect = docker.errors.ImageNotFound("nope")
    with pytest.raises(RuntimeError, match="q-solver install"):
        docker_manager.ensure_container_running()


def test_ensure_container_running_starts_stopped_container(mock_client):
    import docker_manager
    mock_client.images.get.return_value = MagicMock()
    container = MagicMock()
    container.status = "stopped"
    mock_client.containers.get.return_value = container
    docker_manager.ensure_container_running()
    container.start.assert_called_once()


def test_ensure_container_running_creates_container_when_missing(mock_client, monkeypatch):
    import docker_manager
    mock_client.images.get.return_value = MagicMock()
    mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
    monkeypatch.setattr(docker_manager, "get_license", lambda: "dGVzdA==")
    monkeypatch.setattr(docker_manager, "inject_license", lambda c, k: None)
    docker_manager.ensure_container_running()
    mock_client.containers.run.assert_called_once()


def test_handle_license_expiry_removes_container_not_image(mock_client, monkeypatch):
    import docker_manager
    container = MagicMock()
    mock_client.containers.get.return_value = container
    monkeypatch.setattr(docker_manager, "delete_config", lambda: None)
    with pytest.raises(RuntimeError, match="license has expired"):
        docker_manager._handle_license_expiry()
    container.stop.assert_called_once()
    container.remove.assert_called_once()
    mock_client.images.remove.assert_not_called()


def test_pull_base_image_calls_images_pull(mock_client):
    import docker_manager
    docker_manager.pull_base_image(mock_client)
    mock_client.images.pull.assert_called_once_with(docker_manager.BASE_IMAGE)


def test_ensure_buildx_builder_raises_on_unexpected_error(monkeypatch):
    import docker_manager
    import subprocess
    failed = MagicMock()
    failed.returncode = 1
    failed.stderr = "permission denied"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: failed)
    with pytest.raises(RuntimeError, match="docker buildx create failed"):
        docker_manager._ensure_buildx_builder()


def test_build_and_push_multiarch_invokes_buildx(monkeypatch):
    import docker_manager
    import subprocess

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    docker_manager.build_and_push_multiarch(tag="example/kdb-x-runner:test")

    build_cmd = calls[1]
    assert "buildx" in build_cmd
    assert "example/kdb-x-runner:test" in build_cmd
    assert "--push" in build_cmd
    assert str(docker_manager._DOCKERFILE_DIR) in build_cmd


def test_inject_license_writes_kc_lic_via_put_archive():
    import docker_manager
    import tarfile
    import base64

    container = MagicMock()
    license_key = base64.b64encode(b"LICENSE-CONTENT").decode()

    docker_manager.inject_license(container, license_key)

    container.put_archive.assert_called_once()
    path_arg, tar_stream = container.put_archive.call_args[0]
    assert path_arg == "/root/.kx/"

    tar = tarfile.open(fileobj=tar_stream, mode="r")
    member = tar.getmember("kc.lic")
    assert tar.extractfile(member).read() == b"LICENSE-CONTENT"


def test_setup_container_replaces_existing_container(mock_client, monkeypatch):
    import docker_manager
    existing = MagicMock()
    mock_client.containers.get.return_value = existing

    new_container = MagicMock()
    monkeypatch.setattr(docker_manager, "_start_container", lambda client: new_container)
    inject_calls = []
    monkeypatch.setattr(docker_manager, "inject_license", lambda c, k: inject_calls.append((c, k)))

    docker_manager.setup_container("bGljZW5zZQ==")

    mock_client.images.pull.assert_called_once_with(docker_manager.BASE_IMAGE)
    existing.stop.assert_called_once()
    existing.remove.assert_called_once()
    assert inject_calls == [(new_container, "bGljZW5zZQ==")]


def test_ensure_container_running_raises_when_license_missing(mock_client, monkeypatch):
    import docker_manager
    mock_client.images.get.return_value = MagicMock()
    mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
    monkeypatch.setattr(docker_manager, "get_license", lambda: None)
    with pytest.raises(RuntimeError, match="q-solver install"):
        docker_manager.ensure_container_running()
