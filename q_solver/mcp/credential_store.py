import json
import stat
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "q-solver"
CONFIG_PATH = CONFIG_DIR / "config.json"
KX_INSTALL_URL = "https://developer.kx.com/products/kdb-x/install"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(stat.S_IRWXU)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def delete_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def setup_with_license(license_key: str) -> None:
    config = load_config()
    config["license_key"] = license_key
    save_config(config)


def get_license() -> str | None:
    return load_config().get("license_key")
