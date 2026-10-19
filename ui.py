import tkinter as tk
import webbrowser

from PIL import Image, ImageDraw

from steam_cef import StorePage


def make_tray_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 2, size - 2],
                        radius=size // 6, fill=(27, 40, 56, 255))
    d.ellipse([size * 0.22, size * 0.22, size * 0.78, size * 0.78],
              fill=(102, 192, 244, 255))
    d.ellipse([size * 0.42, size * 0.42, size * 0.58, size * 0.58],
              fill=(27, 40, 56, 255))
    return img


class ConfirmDialog:
    #Ask whether to apply the lua / manifest files for the detected store page

    BG     = "#1b2838"
    FG     = "#c6d7e7"
    FG_DIM = "#8ba0b3"
    ACCENT = "#66c0f4"
    BTN_BG = "#2a475e"

    def __init__(self, root: tk.Tk, page: StorePage, tool: str,
                 on_add, on_dismiss, timeout: int = 15):
        self.root = root
        self.page = page
        self.tool = tool
        self.on_add = on_add
        self.on_dismiss = on_dismiss
        self.display_name = page.game_name

        self._closed = False
        self._remaining = timeout
        self._timer_id = None

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.title("Steam Tray")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._dismiss)

        frame = tk.Frame(self.win, padx=16, pady=14, bg=self.BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"Apply manifest?  ({tool})",
                 font=("Segoe UI", 11, "bold"),
                 bg=self.BG, fg=self.FG).pack(anchor="w")

        self.name_label = tk.Label(frame, text=self.display_name,
                                   font=("Segoe UI", 10),
                                   bg=self.BG, fg="#ffffff",
                                   wraplength=340, justify="left")
        self.name_label.pack(anchor="w", pady=(4, 2))

        tk.Label(frame, text=f"App ID: {page.app_id}",
                 font=("Segoe UI", 9),
                 bg=self.BG, fg=self.FG_DIM).pack(anchor="w")

        link = tk.Label(frame, text="Open store page",
                        font=("Segoe UI", 9, "underline"),
                        bg=self.BG, fg=self.ACCENT, cursor="hand2")
        link.pack(anchor="w", pady=(2, 10))
        link.bind("<Button-1>", lambda _e: webbrowser.open(page.url))

        btn_row = tk.Frame(frame, bg=self.BG)
        btn_row.pack(fill="x")

        self.countdown = tk.Label(btn_row, text=f"{self._remaining}s",
                                  font=("Segoe UI", 9),
                                  bg=self.BG, fg=self.FG_DIM)
        self.countdown.pack(side="left")

        tk.Button(btn_row, text="Not now", command=self._dismiss,
                  bg=self.BTN_BG, fg=self.FG,
                  activebackground=self.BTN_BG, activeforeground=self.FG,
                  relief="flat", padx=10, pady=4).pack(side="right", padx=(6, 0))
        tk.Button(btn_row, text="Apply", command=self._add,
                  bg=self.ACCENT, fg=self.BG,
                  activebackground=self.ACCENT, activeforeground=self.BG,
                  relief="flat", padx=14, pady=4).pack(side="right")

        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{max(0, sw - w - 24)}+{max(0, sh - h - 72)}")

        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.focus_force()

        self._tick()

    def set_game_name(self, name: str) -> None:
        if self._closed:
            return
        self.display_name = name
        try:
            self.name_label.config(text=name)
        except tk.TclError:
            pass

    def _tick(self):
        if self._closed:
            return
        self._remaining -= 1
        if self._remaining <= 0:
            self._dismiss()
            return
        try:
            self.countdown.config(text=f"{self._remaining}s")
            self._timer_id = self.win.after(1000, self._tick)
        except tk.TclError:
            pass

    def _cancel_timer(self):
        if self._timer_id is not None:
            try:
                self.win.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

    def _add(self):
        if self._closed:
            return
        self._closed = True
        self._cancel_timer()
        try:
            self.on_add(self.display_name)
        finally:
            try:
                self.win.destroy()
            except tk.TclError:
                pass

    def _dismiss(self):
        if self._closed:
            return
        self._closed = True
        self._cancel_timer()
        try:
            self.on_dismiss()
        finally:
            try:
                self.win.destroy()
            except tk.TclError:
                pass