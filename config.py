import json
import os
from pathlib import Path

APP_NAME = "SteamTray"

_BASE = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
CONFIG_DIR = _BASE / APP_NAME
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "config.json"
DB_FILE     = CONFIG_DIR / "library.db"

HUBCAP_CONFIG_FILE = Path(os.path.expanduser("~")) / ".steam_lookup_hubcap.json"

DEFAULT_CONFIG = {
    "cef_port": 8080,
    "poll_interval": 1.0,
    "auto_dismiss_seconds": 15,
    "probe_interval_seconds": 5,
    "tool": "Steamtools",            # or "OpenSteamTools"
    "auto_restart_steam": False,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)