import json
import os
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import requests

HUBCAP_CONFIG_FILE = os.path.join(
    os.path.expanduser("~"), ".steam_lookup_hubcap.json"
)
HUBCAP_API_BASE = "https://hubcapmanifest.com/api/v1"

_STEAM_CANDIDATES = [
    Path("C:/Program Files (x86)/Steam"),
    Path("C:/Program Files/Steam"),
]

_TOOL_PATHS = {
    "Steamtools":     ("config", "stplug-in"),
    "OpenSteamTools": ("config", "lua"),
}

def load_hubcap_key() -> str:
    try:
        with open(HUBCAP_CONFIG_FILE) as f:
            return (json.load(f).get("api_key") or "").strip()
    except Exception:
        return ""


def save_hubcap_key(key: str) -> bool:
    try:
        data = {}
        if os.path.exists(HUBCAP_CONFIG_FILE):
            try:
                with open(HUBCAP_CONFIG_FILE) as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["api_key"] = key
        with open(HUBCAP_CONFIG_FILE, "w") as f:
            json.dump(data, f)
        return True
    except Exception:
        return False


def get_hubcap_stats(api_key: Optional[str] = None) -> Tuple[Optional[dict], Optional[str], int]:
    api_key = api_key if api_key is not None else load_hubcap_key()
    if not api_key:
        return None, "API key not set", 0
    try:
        resp = requests.get(
            f"{HUBCAP_API_BASE}/user/stats",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json(), None, 200
        return None, f"HTTP {resp.status_code}", resp.status_code
    except Exception as e:
        return None, f"Request failed: {e}", 0


def format_stats(stats: Optional[dict]) -> str:
    if not stats:
        return "n/a"
    parts = []
    u = stats.get("daily_usage")
    lim = stats.get("daily_limit")
    if u is not None and lim is not None:
        parts.append(f"{u}/{lim} today")

    exp = stats.get("api_key_expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = exp_dt - now
            days = delta.days
            if days < 0:
                parts.append("EXPIRED")
            elif days == 0:
                parts.append(f"{delta.seconds // 3600}h left")
            else:
                parts.append(f"{days}d left")
        except Exception:
            pass
    return " \u00b7 ".join(parts) if parts else "n/a"


def stats_detail_text(stats: Optional[dict], error: Optional[str]) -> str:
    if error:
        return f"\u274c {error}"
    if not stats:
        return "No data."
    exp = stats.get("api_key_expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days = (exp_dt - now).days
            exp_line = f"{exp_dt.strftime('%Y-%m-%d %H:%M UTC')}  ({days} days)"
        except Exception:
            exp_line = str(exp)
    else:
        exp_line = "never"

    return "\n".join([
        f"User:              {stats.get('username', 'N/A')}",
        f"Daily usage:       {stats.get('daily_usage', '?')} / {stats.get('daily_limit', '?')}",
        f"Total requests:    {stats.get('api_key_usage_count', '?')}",
        f"Key expires:       {exp_line}",
        f"Can make requests: {'Yes' if stats.get('can_make_requests') else 'No'}",
    ])


def _find_steam_root() -> Optional[Path]:
    for p in _STEAM_CANDIDATES:
        if p.exists():
            return p
    try:
        from steam_utils import find_steam_path
        return find_steam_path()
    except Exception:
        return None

def apply_manifest(app_id: str, tool: str = "Steamtools",
                   api_key: Optional[str] = None) -> str:
    app_id = str(app_id)
    api_key = api_key if api_key is not None else load_hubcap_key()

    if not api_key:
        return (f"\u274c Hubcap API key not set.\n"
                f"Expected at: {HUBCAP_CONFIG_FILE}")

    steam_root = _find_steam_root()
    if not steam_root:
        return "\u274c Steam installation not found."

    depotcache = steam_root / "depotcache"
    sub, leaf = _TOOL_PATHS.get(tool, _TOOL_PATHS["Steamtools"])
    lua_dir = steam_root / sub / leaf

    depotcache.mkdir(parents=True, exist_ok=True)
    lua_dir.mkdir(parents=True, exist_ok=True)

    zip_path = Path.home() / f"manifest_{app_id}.zip"
    temp_dir = Path.home() / f"temp_manifest_{app_id}"

    url = f"{HUBCAP_API_BASE}/manifest/{app_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        if resp.status_code != 200:
            return f"\u274c API error: {resp.status_code} \u2013 {resp.text[:200]}"
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        return f"\u274c Download failed: {e}"

    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True)

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

        return (f"\u2705 Manifests applied successfully for {tool}!\n"
                f"   \u2022 {n_manifest} .manifest \u2192 depotcache\n"
                f"   \u2022 {n_lua} .lua \u2192 {sub}/{leaf}")
    except Exception as e:
        return f"\u274c Extraction failed: {e}"

def is_steam_running() -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
            stderr=subprocess.DEVNULL,
        ).decode(errors="ignore").lower()
        return "steam.exe" in out
    except Exception:
        return False


def restart_steam() -> str:
    steam_root = _find_steam_root()
    steam_exe = (steam_root / "steam.exe") if steam_root else None
    running = is_steam_running()

    if running and steam_exe and steam_exe.exists():
        try:
            subprocess.run([str(steam_exe), "-shutdown"],
                           check=True, timeout=10)
            time.sleep(3)
            if is_steam_running():
                subprocess.run(["taskkill", "/F", "/IM", "steam.exe"],
                               capture_output=True, check=False)
                time.sleep(1)
        except Exception as e:
            return f"\u274c Failed to shut down Steam: {e}"

    if steam_exe and steam_exe.exists():
        try:
            os.startfile(str(steam_exe))  # noqa: S606
            return "\U0001f504 Steam restarted gracefully." if running else "\U0001f504 Steam launched."
        except Exception:
            pass
    try:
        os.startfile("steam://open/games")  # noqa: S606
        return "\U0001f504 Steam launched via URI (fallback)."
    except Exception as e:
        return f"\u274c Failed to launch Steam: {e}"