import re
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

import requests

STORE_URL_RE = re.compile(
    r"^https?://store\.steampowered\.com/app/(\d+)(?:/([^/?#]+))?"
)


@dataclass
class StorePage:
    app_id: str
    slug: str
    url: str
    title: str
    target_id: str
    resolved_name: Optional[str] = field(default=None)

    @property
    def game_name(self) -> str:
        if self.resolved_name:
            return self.resolved_name
        if self.slug:
            return self.slug.replace("-", " ").replace("_", " ").title()
        t = (self.title or "").strip()
        if t.endswith(" on Steam"):
            t = t[: -len(" on Steam")]
        return t or f"App {self.app_id}"


def parse_store_url(url: str) -> Optional[Tuple[str, str]]:
    m = STORE_URL_RE.match(url or "")
    if not m:
        return None
    return m.group(1), (m.group(2) or "")


def fetch_app_name(app_id: str, timeout: float = 2.0) -> Optional[str]:
    try:
        r = requests.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": app_id, "filters": "basic", "cc": "us", "l": "en"},
            timeout=timeout,
        )
        entry = r.json().get(str(app_id), {})
        if entry.get("success"):
            return entry["data"].get("name")
    except Exception:
        pass
    return None


class CefMonitor:

    def __init__(
        self,
        port: int = 8080,
        interval: float = 1.0,
        on_store_page: Optional[Callable[[StorePage], None]] = None,
    ):
        self.port = port
        self.interval = interval
        self.on_store_page = on_store_page
        self._stop = threading.Event()
        self._seen: set = set()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop.clear()
        self._seen.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="cef-monitor")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _list_targets(self):
        try:
            r = requests.get(f"http://127.0.0.1:{self.port}/json/list",
                             timeout=1.0)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def _run(self):
        while not self._stop.is_set():
            targets = self._list_targets()

            current: Dict[Tuple[str, str], Tuple[dict, Tuple[str, str]]] = {}
            for t in targets:
                tid = t.get("id")
                if not tid:
                    continue
                parsed = parse_store_url(t.get("url", ""))
                if parsed:
                    current[(tid, parsed[0])] = (t, parsed)

            new_keys = set(current) - self._seen
            self._seen = set(current)

            for key in new_keys:
                t, (app_id, slug) = current[key]
                page = StorePage(
                    app_id=app_id,
                    slug=slug,
                    url=t.get("url", ""),
                    title=t.get("title", ""),
                    target_id=key[0],
                )
                try:
                    if self.on_store_page:
                        self.on_store_page(page)
                except Exception as e:
                    print(f"[cef] callback error: {e}")

            self._stop.wait(self.interval)

    def dump_targets(self):
        return self._list_targets()