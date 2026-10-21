import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from steam_utils import find_steam_path


def _get_paths(steam_folder: Path) -> dict:
    return {
        "stplugin":          steam_folder / "config" / "stplug-in",
        "config_depotcache": steam_folder / "config" / "depotcache",
        "depotcache":        steam_folder / "depotcache",
        "stui":              steam_folder / "config" / "stUI",
        "stats":             steam_folder / "config" / "StatsExport",
        "lua":               steam_folder / "config" / "lua",
    }


def remove_game(app_id: str,
                steam_folder: Optional[Path] = None
                ) -> Tuple[int, List[str]]:
    app_id = str(app_id).strip()
    if not app_id.isdigit() or len(app_id) < 2:
        return 0, [f"Invalid app ID: {app_id!r}"]

    steam_folder = steam_folder or find_steam_path()
    if not steam_folder:
        return 0, ["Steam installation not found."]

    paths = _get_paths(steam_folder)
    pattern = re.compile(rf"{app_id[0:-1]}\d\D+")

    log: List[str] = []
    count = 0

    for key, path in paths.items():
        if not path.exists():
            continue
        try:
            names = os.listdir(path)
        except Exception as e:
            log.append(f"Cannot list {path}: {e}")
            continue

        for name in names:
            full = path / name
            if not full.is_file():
                continue
            if key == "stats":
                matched = f"_{app_id}_" in name
            else:
                matched = bool(pattern.match(name))
            if not matched:
                continue
            try:
                full.unlink()
                count += 1
                log.append(f"Deleted: {full}")
            except Exception as e:
                log.append(f"Error deleting {full}: {e}")

    return count, log


def remove_all_games(steam_folder: Optional[Path] = None
                     ) -> Tuple[int, List[str]]:
    steam_folder = steam_folder or find_steam_path()
    if not steam_folder:
        return 0, ["Steam installation not found."]

    paths = _get_paths(steam_folder)
    log: List[str] = []
    count = 0

    for path in paths.values():
        if not path.exists():
            continue
        try:
            names = os.listdir(path)
        except Exception as e:
            log.append(f"Cannot list {path}: {e}")
            continue

        for name in names:
            if not name.endswith((".st", ".manifest", ".bin")):
                continue
            full = path / name
            if not full.is_file():
                continue
            try:
                full.unlink()
                count += 1
                log.append(f"Deleted: {full}")
            except Exception as e:
                log.append(f"Error deleting {full}: {e}")

    return count, log
