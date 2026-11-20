"""Ryuu manifest API client for SteamTray."""
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional

import requests

from config import load_config, save_config

RYUU_API_BASE = "https://generator.ryuu.lol"

_STEAM_CANDIDATES = [
    Path("C:/Program Files (x86)/Steam"),
    Path("C:/Program Files/Steam"),
]

_TOOL_PATHS = {
    "Steamtools": ("config", "stplug-in"),
    "OpenSteamTool": ("config", "lua"),
    "Ryuu OpenSteamTool": ("config", "lua"),
}


def load_ryuu_key() -> str:
    return (load_config().get("ryuu_api_key") or "").strip()


def save_ryuu_key(key: str) -> bool:
    try:
        cfg = load_config()
        cfg["ryuu_api_key"] = key.strip()
        save_config(cfg)
        return True
    except Exception:
        return False


def _find_steam_root() -> Optional[Path]:
    for p in _STEAM_CANDIDATES:
        if p.exists():
            return p
    try:
        from steam_utils import find_steam_path
        return find_steam_path()
    except Exception:
        return None


def _auth_headers(api_key: str) -> dict:
    return {"X-Auth-Key": api_key}


def request_update(app_id: str, api_key: str, branch: str = "public") -> bool:
    try:
        r = requests.get(
            f"{RYUU_API_BASE}/requestupdate",
            headers=_auth_headers(api_key),
            params={"appid": app_id, "branch": branch},
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


def request_game(app_id: str, api_key: str) -> bool:
    try:
        r = requests.get(
            f"{RYUU_API_BASE}/request",
            headers=_auth_headers(api_key),
            params={"appid": app_id},
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


def request_branch(app_id: str, api_key: str, branch: str) -> bool:
    try:
        r = requests.get(
            f"{RYUU_API_BASE}/requestbranch",
            headers=_auth_headers(api_key),
            params={"appid": app_id, "branch": branch},
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


def _download_zip(app_id: str, api_key: str, branch: str,
                  dest: Path):
    params = {}
    if branch and branch != "public":
        params["branch"] = branch
    try:
        resp = requests.get(
            f"{RYUU_API_BASE}/api/download/{app_id}",
            headers=_auth_headers(api_key),
            params=params or None,
            stream=True,
            timeout=60,
        )
        if resp.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True, resp
        return False, resp
    except Exception:
        return False, None


def apply_manifest(app_id: str, tool: str = "Steamtools",
                   api_key: Optional[str] = None,
                   branch: str = "public") -> str:
    app_id = str(app_id)
    api_key = api_key if api_key is not None else load_ryuu_key()

    if not api_key:
        return ("\u274c Ryuu API key not set.\n"
                "Set it via the tray menu: Set Ryuu key\u2026")

    steam_root = _find_steam_root()
    if not steam_root:
        return "\u274c Steam installation not found."

    depotcache = steam_root / "depotcache"
    sub, leaf = _TOOL_PATHS.get(tool, _TOOL_PATHS["Steamtools"])
    lua_dir = steam_root / sub / leaf

    depotcache.mkdir(parents=True, exist_ok=True)
    lua_dir.mkdir(parents=True, exist_ok=True)

    zip_path = Path.home() / f"ryuu_manifest_{app_id}.zip"
    temp_dir = Path.home() / f"temp_ryuu_manifest_{app_id}"

    ok, resp = _download_zip(app_id, api_key, branch, zip_path)

    if not ok and resp is not None and resp.status_code == 404:
        request_update(app_id, api_key, branch)
        request_game(app_id, api_key)
        time.sleep(3)
        ok, resp = _download_zip(app_id, api_key, branch, zip_path)

    if not ok:
        code = resp.status_code if resp is not None else "?"
        body = resp.text[:200] if resp is not None else "no response"
        return (f"\u274c Ryuu API error: {code} \u2013 {body}\n"
                f"   Tip: the app may still be generating; retry in a minute.")

    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        n_manifest, n_lua = 0, 0
        for file in temp_dir.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix == ".manifest":
                shutil.copy(file, depotcache / file.name)
                n_manifest += 1
            elif file.suffix == ".lua":
                shutil.copy(file, lua_dir / file.name)
                n_lua += 1

        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            zip_path.unlink()
        except FileNotFoundError:
            pass

        return (f"\u2705 Ryuu manifests applied successfully for {tool}!\n"
                f"   \u2022 {n_manifest} .manifest \u2192 depotcache\n"
                f"   \u2022 {n_lua} .lua \u2192 {sub}/{leaf}")
    except Exception as e:
        return f"\u274c Extraction failed: {e}"