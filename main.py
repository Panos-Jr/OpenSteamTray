import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import os
import pystray
from pystray import Menu, MenuItem as Item

import hubcap
import remover
from config import APP_NAME, CONFIG_DIR, load_config, save_config
from library import Library
from steam_cef import CefMonitor, StorePage, fetch_app_name
from steam_utils import (
    enable_cef_debugging,
    find_steam_path,
    get_installed_app_ids,
    is_cef_debugging_enabled,
    is_steam_running,
    open_folder,
)
from ui import ConfirmDialog, make_tray_image


STATS_REFRESH_MS = 5 * 60 * 1000   # auto-refresh API_KEY stats every 5 minutes


class SteamTrayApp:
    def __init__(self):
        self.cfg = load_config()
        self.lib = Library()
        self.events: "queue.Queue" = queue.Queue()

        self.monitor: CefMonitor | None = None
        self.cef_status = False

        self.root: tk.Tk | None = None
        self.icon: pystray.Icon | None = None

        self.stats_cache: dict | None = None
        self.stats_error: str | None = None

    def run(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.icon = pystray.Icon(
            APP_NAME, make_tray_image(), APP_NAME, menu=self._build_menu(),
        )
        try:
            self.icon.run_detached()
        except NotImplementedError:
            threading.Thread(target=self.icon.run, daemon=True).start()

        self.root.after(200, self._ensure_monitor)
        self.root.after(150, self._process_events)
        self.root.after(500, lambda: self.events.put(("refresh_stats", None)))
        self.root.after(STATS_REFRESH_MS, self._auto_refresh_stats)

        self.root.mainloop()

    def _auto_refresh_stats(self):
        self.events.put(("refresh_stats", None))
        if self.root:
            self.root.after(STATS_REFRESH_MS, self._auto_refresh_stats)

    # menu
    def _stats_label(self) -> str:
        if self.stats_error:
            return f"Hubcap: {self.stats_error[:40]}"
        if self.stats_cache is None:
            return "Hubcap: loading\u2026"
        return f"Hubcap: {hubcap.format_stats(self.stats_cache)}"

    def _build_menu(self) -> Menu:
        def make_remove_handler(app_id: str, name: str):
            def handler(icon, item):
                self.events.put(("remove_game", (app_id, name)))
            return handler

        def make_tool_checked(tool_name: str):
            def is_checked(item):
                return self.cfg["tool"] == tool_name
            return is_checked

        def act_show_stats(icon, item):
            self.events.put(("show_stats", None))

        def act_refresh_stats(icon, item):
            self.events.put(("refresh_stats", None))

        def act_apply_by_id(icon, item):
            self.events.put(("apply_by_id", None))

        def act_remove_by_id(icon, item):
            self.events.put(("remove_by_id", None))

        def act_remove_all(icon, item):
            self.events.put(("remove_all", None))

        # submenus
        tool_items = [
            Item(name, self._set_tool,
                 checked=make_tool_checked(name),
                 radio=True)
            for name in ("Steamtools", "OpenSteamTools")
        ]

        rows = self.lib.all()[:20]
        if rows:
            lib_items = [
                Item(f"{name}  ({app_id})", make_remove_handler(app_id, name))
                for app_id, name, _u, _a in rows
            ]
        else:
            lib_items = [Item("(empty)", None, enabled=False)]

        return Menu(
            Item(f"Steam debugging: {'ON' if self.cef_status else 'OFF'}",
                 None, enabled=False),
            Item("Enable Steam debugging", self._enable_debugging),
            Item("Dump CEF targets", self._dump_targets),
            Menu.SEPARATOR,
            Item(self._stats_label(), act_show_stats),
            Item("Refresh stats", act_refresh_stats),
            Item("Set Hubcap key\u2026", lambda: self.root.after(0, lambda: self._set_hubcap_key())),
            Item("Apply tool", Menu(*tool_items)),
            Item("Apply manifest by App ID\u2026", act_apply_by_id),
            Menu.SEPARATOR,
            Item("Applied", Menu(*lib_items)),
            Item("Remove game by App ID\u2026", act_remove_by_id),
            Item("Remove ALL games\u2026", act_remove_all),
            Menu.SEPARATOR,
            Item("Open data folder", self._open_data_folder),
            Menu.SEPARATOR,
            Item("Quit", self._quit),
        )

    def _rebuild_menu(self):
        if not self.icon:
            return
        try:
            self.icon.menu = self._build_menu()
            self.icon.update_menu()
        except Exception as e:
            print(f"[tray] menu rebuild failed: {e}")

    def _ensure_monitor(self):
        enabled = is_cef_debugging_enabled(self.cfg["cef_port"])

        if enabled and self.monitor is None:
            self.monitor = CefMonitor(
                port=self.cfg["cef_port"],
                interval=self.cfg["poll_interval"],
                on_store_page=lambda p: self.events.put(("store_page", p)),
            )
            self.monitor.start()
            print("[cef] monitor started")
        elif not enabled and self.monitor is not None:
            self.monitor.stop()
            self.monitor = None
            print("[cef] monitor stopped")

        if enabled != self.cef_status:
            self.cef_status = enabled
            self._rebuild_menu()

        if self.root:
            self.root.after(int(self.cfg["probe_interval_seconds"] * 1000),
                            self._ensure_monitor)

    def _process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                try:
                    if kind == "store_page":
                        self._handle_store_page(payload)
                    elif kind == "apply_result":
                        self._handle_apply_result(*payload)
                    elif kind == "remove_game":
                        self._do_remove_game(*payload)
                    elif kind == "remove_by_id":
                        self._do_remove_by_id()
                    elif kind == "remove_all":
                        self._do_remove_all()
                    elif kind == "apply_by_id":
                        self._do_apply_by_id()
                    elif kind == "refresh_stats":
                        self._refresh_stats_async()
                    elif kind == "stats_loaded":
                        self._on_stats_loaded(*payload)
                    elif kind == "restart_done":
                        self._handle_restart_done(payload)
                    elif kind == "show_stats":
                        self._do_show_stats()
                except Exception as e:
                    print(f"[events] handler for {kind!r} failed: {e}")
        except queue.Empty:
            pass
        if self.root:
            self.root.after(150, self._process_events)

    # store-page prompt, check if excluded by user before
    def _handle_store_page(self, page: StorePage):
        if self.lib.has(page.app_id) or self.lib.is_dismissed(page.app_id):
            return
        try:
            if page.app_id in get_installed_app_ids(find_steam_path()):
                return
        except Exception:
            pass

        dlg = ConfirmDialog(
            self.root, page,
            tool=self.cfg["tool"],
            on_add=lambda name: self._apply(page, name),
            on_dismiss=lambda: self.lib.dismiss(page.app_id),
            timeout=int(self.cfg["auto_dismiss_seconds"]),
        )

        def worker():
            name = fetch_app_name(page.app_id)
            if name and self.root:
                try:
                    self.root.after(0, lambda: dlg.set_game_name(name))
                except tk.TclError:
                    pass

        threading.Thread(target=worker, daemon=True,
                         name=f"name-{page.app_id}").start()

    def _apply(self, page: StorePage, name: str):
        tool = self.cfg["tool"]
        self.lib.add(page.app_id, name, page.url)
        self._rebuild_menu()
        self._notify("Applying manifest", f"{name} ({page.app_id}) \u2192 {tool}")

        def worker():
            result = hubcap.apply_manifest(page.app_id, tool=tool)
            self.events.put(("apply_result", (name, result)))

        threading.Thread(target=worker, daemon=True,
                         name=f"apply-{page.app_id}").start()

    def _handle_apply_result(self, name: str, result: str):
        ok = result.startswith("\u2705")
        title = "Manifest applied" if ok else "Manifest failed"
        print(f"[apply] {title}: {name}\n{result}")

        # Tray notification only
        self._notify(
            title,
            f"{name} \u2014 {result.splitlines()[0][:120]}",
        )

        self.events.put(("refresh_stats", None))

        if not ok:
            return

        if self.cfg.get("auto_restart_steam", False):
            self._restart_steam_async()
            return

        try:
            if messagebox.askyesno(
                "Restart Steam",
                "Manifests applied successfully.\n"
                "Steam must be restarted for the new game to appear.\n"
                "Restart now?",
            ):
                self._restart_steam_async()
        except tk.TclError:
            pass

    def _restart_steam_async(self):
        print("[restart] starting\u2026")
        if self.icon:
            try:
                self.icon.title = f"{APP_NAME} \u2014 restarting Steam\u2026"
            except Exception:
                pass

        def worker():
            msg = hubcap.restart_steam()
            self.events.put(("restart_done", msg))

        threading.Thread(target=worker, daemon=True,
                         name="restart-steam").start()
        
    def _handle_restart_done(self, msg: str):
        print(f"[restart] {msg}")
        if self.icon:
            try:
                self.icon.title = APP_NAME
            except Exception:
                pass

    def _do_apply_by_id(self):
        #done manually by app_id if excluded, or is a delisted game
        try:
            raw = simpledialog.askstring(
                "Apply manifest",
                "Enter the Steam App ID:",
                parent=self.root,
            )
        except tk.TclError:
            return
        if not raw:
            return
        app_id = raw.strip()
        if not app_id.isdigit():
            messagebox.showerror("Invalid ID", f"{raw!r} is not a valid App ID.")
            return

        name = fetch_app_name(app_id) or f"App {app_id}"
        self.lib.add(app_id, name, f"https://store.steampowered.com/app/{app_id}")
        self._rebuild_menu()

        def worker():
            result = hubcap.apply_manifest(app_id, tool=self.cfg["tool"])
            self.events.put(("apply_result", (name, result)))

        threading.Thread(target=worker, daemon=True,
                         name=f"apply-{app_id}").start()

    # ------------------------------------------------------------------ remove
    def _do_remove_game(self, app_id: str, name: str):
        """Confirm and remove a single game's files."""
        try:
            ok = messagebox.askyesno(
                "Remove game",
                f"Remove files for:\n\n{name}\nApp ID: {app_id}\n\n"
                f"Deletes matching .st / .manifest / .lua files from "
                f"depotcache, config\\stplug-in, config\\lua, config\\depotcache,\n"
                f"config\\stUI and config\\StatsExport.",
            )
        except tk.TclError:
            return
        if not ok:
            return

        count, log = remover.remove_game(app_id)
        self.lib.remove(app_id)
        self._rebuild_menu()

        for line in log:
            print(f"[remove] {line}")
        msg = f"Removed {count} file(s)." if count else "No matching files were found."
        try:
            messagebox.showinfo("Removal complete", f"{name}\n\n{msg}")
        except tk.TclError:
            pass

    def _do_remove_by_id(self):
        try:
            raw = simpledialog.askstring(
                "Remove game",
                "Enter the Steam App ID to remove:",
                parent=self.root,
            )
        except tk.TclError:
            return
        if not raw:
            return
        app_id = raw.strip()
        if not app_id.isdigit():
            messagebox.showerror("Invalid ID", f"{raw!r} is not a valid App ID.")
            return
        name = f"App {app_id}"
        try:
            row = next((r for r in self.lib.all() if r[0] == app_id), None)
            if row:
                name = row[1]
        except Exception:
            pass
        self._do_remove_game(app_id, name)

    def _do_remove_all(self):
        try:
            ok = messagebox.askyesno(
                "Remove ALL games",
                "This will delete every .st, .manifest and .bin file from:\n\n"
                "\u2022 depotcache\n"
                "\u2022 config\\depotcache\n"
                "\u2022 config\\stplug-in\n"
                "\u2022 config\\lua\n"
                "\u2022 config\\stUI\n"
                "\u2022 config\\StatsExport\n\n"
                "This cannot be undone. Continue?",
            )
        except tk.TclError:
            return
        if not ok:
            return

        count, log = remover.remove_all_games()
        self.lib.clear()
        self._rebuild_menu()

        for line in log:
            print(f"[remove-all] {line}")
        msg = f"Removed {count} file(s)." if count else "No matching files were found."
        try:
            messagebox.showinfo("Removal complete", msg)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ stats
    def _refresh_stats_async(self):
        def worker():
            stats, err = hubcap.get_hubcap_stats()
            if err is not None:
                self._notify("Update your API key", "Your api key may be expired/invalid")
                import webbrowser

                webbrowser.open("https://hubcapmanifest.com/api-keys/stats")

            self.events.put(("stats_loaded", (stats, err)))
        threading.Thread(target=worker, daemon=True, name="stats").start()

    def _on_stats_loaded(self, stats, error):
        self.stats_cache = stats
        self.stats_error = error
        self._rebuild_menu()

    def _do_show_stats(self):
        if self.stats_error:
            text = f"\u274c {self.stats_error}"
        elif self.stats_cache is None:
            text = "No data yet \u2014 try 'Refresh stats'."
        else:
            text = hubcap.stats_detail_text(self.stats_cache, None)
        try:
            messagebox.showinfo("Hubcap stats", text)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ menu actions
    def _set_tool(self, _icon, item):
        self.cfg["tool"] = item.text
        save_config(self.cfg)
        self._rebuild_menu()

    def _set_hubcap_key(self, _icon=None, _item=None):
        current = hubcap.load_hubcap_key()

        self.root.update_idletasks()
        try:
            key = simpledialog.askstring(
                "Hubcap API key",
                f"Enter your Hubcap manifest API key.\n"
                f"(Stored in {hubcap.HUBCAP_CONFIG_FILE})",
                initialvalue=current, show="\u2022"
            )
        except tk.TclError as e:
            print('tk error', e)
            return
        if not key:
            return
        if hubcap.save_hubcap_key(key.strip()):
            self._notify("Hubcap key saved", "Refreshing stats\u2026")
            self._rebuild_menu()
            self._notify("Complete", "Stats refreshed successfully")
            self.events.put(("refresh_stats", None))
        else:
            self._notify("Save failed", "Could not write the key file.")

    def _enable_debugging(self, _icon=None, _item=None):
        ok, msg = enable_cef_debugging()
        if ok:
            self._notify(
                "Steam debugging enabled",
                "Restart Steam for the change to take effect."
                if is_steam_running() else "Start Steam to begin monitoring.",
            )
        else:
            self._notify("Could not enable debugging", msg)

    def _dump_targets(self, _icon=None, _item=None):
        if not self.monitor:
            self._notify("CEF monitor not running",
                         "Enable debugging and restart Steam.")
            return
        targets = self.monitor.dump_targets()
        print(f"[cef] {len(targets)} target(s):")
        for t in targets:
            print(f"  id={t.get('id')}  type={t.get('type')}  "
                  f"title={t.get('title')!r}  url={t.get('url')!r}")

    def _open_data_folder(self, _icon=None, _item=None):
        open_folder(CONFIG_DIR)

    def _quit(self, _icon=None, _item=None):
        if not self.root:
            os._exit(0)
            return
        try:
            self.root.after(0, self._shutdown)
        except Exception:
            os._exit(0)

    def _shutdown(self):
        # Stop the CEF poller first so it can't re-enter anything.
        if self.monitor:
            try:
                self.monitor.stop()
            except Exception:
                pass
            self.monitor = None

        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

        os._exit(0)

    def _notify(self, title: str, msg: str):
        try:
            if self.icon:
                self.icon.notify(msg, title)
                return
        except Exception:
            pass
        print(f"[notify] {title}: {msg}")


def main():
    SteamTrayApp().run()


if __name__ == "__main__":
    main()