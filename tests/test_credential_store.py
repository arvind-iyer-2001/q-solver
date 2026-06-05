import pytest
import json
import stat
from pathlib import Path


def test_load_config_returns_empty_when_missing(tmp_path):
    import credential_store
    credential_store.CONFIG_PATH = tmp_path / "config.json"
    credential_store.CONFIG_DIR = tmp_path
    assert credential_store.load_config() == {}


def test_save_config_writes_json_with_600_perms(tmp_path):
    import credential_store
    credential_store.CONFIG_PATH = tmp_path / "config.json"
    credential_store.CONFIG_DIR = tmp_path
    credential_store.save_config({"license_key": "abc123"})
    path = tmp_path / "config.json"
    assert json.loads(path.read_text()) == {"license_key": "abc123"}
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_delete_config_removes_file(tmp_path):
    import credential_store
    config_path = tmp_path / "config.json"
    config_path.write_text('{"license_key": "abc"}')
    credential_store.CONFIG_PATH = config_path
    credential_store.delete_config()
    assert not config_path.exists()


def test_delete_config_noop_when_missing(tmp_path):
    import credential_store
    credential_store.CONFIG_PATH = tmp_path / "nonexistent.json"
    credential_store.delete_config()  # must not raise


def test_setup_with_license_saves_key(tmp_path):
    import credential_store
    credential_store.CONFIG_PATH = tmp_path / "config.json"
    credential_store.CONFIG_DIR = tmp_path
    credential_store.setup_with_license("mykey123")
    assert credential_store.load_config()["license_key"] == "mykey123"


def test_get_license_returns_stored_key(tmp_path):
    import credential_store
    config_path = tmp_path / "config.json"
    config_path.write_text('{"license_key": "stored_key"}')
    credential_store.CONFIG_PATH = config_path
    credential_store.CONFIG_DIR = tmp_path
    assert credential_store.get_license() == "stored_key"


def test_get_license_returns_none_when_missing(tmp_path):
    import credential_store
    credential_store.CONFIG_PATH = tmp_path / "config.json"
    credential_store.CONFIG_DIR = tmp_path
    assert credential_store.get_license() is None
