import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Set

import requests

def find_steam_path() -> Optional[Path]:
    system = platform.system()

    if system == "Windows":
        try:
            import winreg  # type: ignore
            for hive, key, value in (
                (winreg.HKEY_CURRENT_USER,  r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        val, _ = winreg.QueryValueEx(k, value)
                        p = Path(val)
                        if p.exists():
                            return p
                except FileNotFoundError:
                    continue
        except ImportError:
            pass
        for candidate in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
            if Path(candidate).exists():
                return Path(candidate)

    elif system == "Darwin":
        p = Path.home() / "Library/Application Support/Steam"
        if p.exists():
            return p

    else:  # Linux
        for p in (Path.home() / ".steam/steam",
                  Path.home() / ".local/share/Steam",
                  Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam"):
            if p.exists():
                return p

    return None

def is_cef_debugging_enabled(port: int = 8080, timeout: float = 0.5) -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def enable_cef_debugging(steam_path: Optional[Path] = None):
    """Create Steam's marker file. Requires a Steam restart to take effect."""
    steam_path = steam_path or find_steam_path()
    if not steam_path:
        return False, "Steam installation not found."
    marker = steam_path / ".cef-enable-remote-debugging"
    try:
        marker.touch(exist_ok=True)
        return True, str(marker)
    except Exception as e:
        return False, str(e)


def is_steam_running() -> bool:
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
                text=True, stderr=subprocess.DEVNULL,
            )
            return "steam.exe" in out.lower()
        out = subprocess.check_output(["pgrep", "-x", "steam"],
                                      text=True, stderr=subprocess.DEVNULL)
        return bool(out.strip())
    except Exception:
        return False


def get_installed_app_ids(steam_path: Optional[Path] = None) -> Set[str]:
    steam_path = steam_path or find_steam_path()
    ids: Set[str] = set()
    if not steam_path:
        return ids

    roots = [steam_path]
    lf = steam_path / "steamapps" / "libraryfolders.vdf"
    if lf.exists():
        try:
            text = lf.read_text(errors="ignore")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(m.group(1).replace("\\\\", "\\"))
                if p.exists():
                    roots.append(p)
        except Exception:
            pass

    for root in roots:
        sa = root / "steamapps"
        if not sa.exists():
            continue
        for f in sa.glob("appmanifest_*.acf"):
            m = re.match(r"appmanifest_(\d+)\.acf$", f.name)
            if m:
                ids.add(m.group(1))
    return ids

def open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])