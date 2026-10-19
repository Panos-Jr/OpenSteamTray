import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from config import DB_FILE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    app_id     TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    url        TEXT,
    added_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dismissed (
    app_id       TEXT PRIMARY KEY,
    dismissed_at TEXT NOT NULL
);
"""


class Library:
    def __init__(self, path: Path = DB_FILE):
        self.path = path
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def has(self, app_id: str) -> bool:
        with self._conn() as c:
            return c.execute(
                "SELECT 1 FROM library WHERE app_id=?", (app_id,)
            ).fetchone() is not None

    def is_dismissed(self, app_id: str) -> bool:
        with self._conn() as c:
            return c.execute(
                "SELECT 1 FROM dismissed WHERE app_id=?", (app_id,)
            ).fetchone() is not None

    def all(self) -> List[Tuple[str, str, str, str]]:
        with self._conn() as c:
            return c.execute(
                "SELECT app_id, name, url, added_at FROM library "
                "ORDER BY added_at DESC"
            ).fetchall()

    def add(self, app_id: str, name: str, url: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO library(app_id, name, url, added_at) "
                "VALUES (?,?,?,?)",
                (app_id, name, url, datetime.utcnow().isoformat(timespec="seconds")),
            )
            c.execute("DELETE FROM dismissed WHERE app_id=?", (app_id,))

    def remove(self, app_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM library WHERE app_id=?", (app_id,))
            c.execute("DELETE FROM dismissed WHERE app_id=?", (app_id,))

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM library")

    def dismiss(self, app_id: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO dismissed(app_id, dismissed_at) "
                "VALUES (?,?)",
                (app_id, datetime.utcnow().isoformat(timespec="seconds")),
            )

    def undismiss(self, app_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM dismissed WHERE app_id=?", (app_id,))