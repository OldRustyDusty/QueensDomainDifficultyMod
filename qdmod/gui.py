"""tkinter window: pick the game folder, see what's installed, choose a preset, Apply."""
import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import appdata, gamedetect, installer, procs
from .errors import GameRunningError, ModError
from .presets import EASY, NORMAL, PRESETS, STORY
from .version import APP_NAME, __version__

log = logging.getLogger(__name__)

# Palette
BG = "#f6f4f8"
CARD = "#ffffff"
BORDER = "#dcd6e4"
ACCENT = "#6b3fa0"        # royal purple
ACCENT_DARK = "#4e2a7a"
ACCENT_SOFT = "#f0e8fa"
GOLD = "#d9a62e"
TEXT = "#231d2b"
MUTED = "#6f6680"
OK = "#2e7d32"
WARN = "#b26a00"
ERR = "#c62828"


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def _enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class PresetCard(tk.Frame):
    """A clickable card that behaves like a radio button."""

    def __init__(self, master, preset, variable, scale, on_select):
        super().__init__(master, bg=CARD, highlightthickness=2, highlightbackground=BORDER,
                         highlightcolor=BORDER, cursor="hand2")
        self.preset, self.var, self.on_select = preset, variable, on_select
        pad = int(12 * scale)
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x", padx=pad, pady=(pad, 2))
        self.dot = tk.Canvas(top, width=int(18 * scale), height=int(18 * scale), bg=CARD,
                             highlightthickness=0)
        self.dot.pack(side="left", padx=(0, int(8 * scale)))
        self.title = tk.Label(top, text=preset.title, font=("Segoe UI Semibold", 13), bg=CARD, fg=TEXT)
        self.title.pack(side="left")
        self.badge = tk.Label(top, text=" INSTALLED ", font=("Segoe UI", 8, "bold"), bg=OK, fg="white")
        self.tag = tk.Label(self, text=preset.tagline, font=("Segoe UI", 9, "italic"), bg=CARD, fg=MUTED,
                            anchor="w", justify="left")
        self.tag.pack(fill="x", padx=(pad + int(26 * scale), pad))
        self.lines = []
        for line in preset.details:
            lbl = tk.Label(self, text="•  " + line, font=("Segoe UI", 10), bg=CARD, fg=TEXT,
                           anchor="w", justify="left")
            lbl.pack(fill="x", padx=(pad + int(26 * scale), pad))
            self.lines.append(lbl)
        tk.Frame(self, height=pad, bg=CARD).pack()
        self._scale = scale
        for w in self._all_widgets(self):
            w.bind("<Button-1>", self._clicked)
        variable.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def _all_widgets(self, w):
        yield w
        for c in w.winfo_children():
            yield from self._all_widgets(c)

    def _clicked(self, _event=None):
        if str(self.cget("cursor")) == "arrow":  # disabled while working
            return
        self.var.set(self.preset.key)
        self.on_select()

    def set_installed(self, installed):
        if installed:
            self.badge.pack(side="left", padx=(int(10 * self._scale), 0))
        else:
            self.badge.pack_forget()

    def set_enabled(self, enabled):
        for w in self._all_widgets(self):
            try:
                w.configure(cursor="hand2" if enabled else "arrow")
            except tk.TclError:
                pass

    def refresh(self):
        selected = self.var.get() == self.preset.key
        bg = ACCENT_SOFT if selected else CARD
        self.configure(highlightbackground=ACCENT if selected else BORDER,
                       highlightcolor=ACCENT if selected else BORDER)
        for w in self._all_widgets(self):
            if w is not self.badge:
                w.configure(bg=bg)
        s = self._scale
        d = self.dot
        d.delete("all")
        r = int(16 * s)
        d.create_oval(1, 1, r, r, outline=ACCENT if selected else "#9a90a8", width=max(1, int(2 * s)))
        if selected:
            d.create_oval(int(5 * s), int(5 * s), r - int(4 * s), r - int(4 * s), fill=ACCENT, outline=ACCENT)


class ProgressBar(tk.Canvas):
    """Thin progress bar in the accent colour (ttk's native one ignores custom colours)."""

    def __init__(self, master, height):
        super().__init__(master, height=height, bg=BG, highlightthickness=0)
        self.fraction = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, fraction):
        self.fraction = max(0.0, min(1.0, fraction))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), int(self.cget("height"))
        self.create_rectangle(0, 0, w, h, fill=BORDER, outline=BORDER)
        if self.fraction > 0:
            self.create_rectangle(0, 0, max(h, int(w * self.fraction)), h, fill=ACCENT, outline=ACCENT)


def _elide_middle(text, font, max_px):
    if font.measure(text) <= max_px:
        return text
    keep = len(text)
    while keep > 8:
        keep -= 2
        head, tail = text[:keep // 2], text[len(text) - keep // 2:]
        candidate = head + "…" + tail
        if font.measure(candidate) <= max_px:
            return candidate
    return text[:8] + "…"


class App:
    def __init__(self, root):
        self.root = root
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.game_dir = None
        self.status = None
        self.events = queue.Queue()
        self.worker = None
        self.preset_var = tk.StringVar(value=EASY.key)
        self._build()
        root.after(50, self.detect_game)

    # ----------------------------------------------------------------- layout
    def _build(self):
        s = self.scale
        root = self.root
        root.title(f"{APP_NAME} {__version__}")
        root.configure(bg=BG)
        root.minsize(int(600 * s), int(560 * s))
        try:
            root.iconbitmap(default=resource_path("assets", "icon.ico"))
        except tk.TclError:
            pass

        style = ttk.Style(root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        self.content_w = int(600 * s)

        pad = int(18 * s)
        # Header band
        header = tk.Frame(root, bg=ACCENT_DARK)
        header.pack(fill="x")
        tk.Label(header, text="♛", font=("Segoe UI Symbol", 26), bg=ACCENT_DARK, fg=GOLD) \
            .pack(side="left", padx=(pad, int(8 * s)), pady=int(10 * s))
        ht = tk.Frame(header, bg=ACCENT_DARK)
        ht.pack(side="left", pady=int(10 * s))
        tk.Label(ht, text="Queen's Domain Difficulty Mod", font=("Segoe UI Semibold", 16),
                 bg=ACCENT_DARK, fg="white").pack(anchor="w")
        tk.Label(ht, text=f"Version {__version__}  ·  Choose how hard the game is. Undo any time with Normal.",
                 font=("Segoe UI", 9), bg=ACCENT_DARK, fg="#d8c8ee").pack(anchor="w")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=pad, pady=(int(12 * s), pad))

        # Game folder
        self._section(body, "GAME FOLDER")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        self.path_lbl = tk.Label(row, text="Looking for Queen's Domain…", font=("Segoe UI", 10),
                                 bg=BG, fg=TEXT, anchor="w")
        self.path_lbl.pack(side="left", fill="x", expand=True)
        self.browse_btn = ttk.Button(row, text="Browse…", command=self.browse)
        self.browse_btn.pack(side="right")
        self.found_lbl = tk.Label(body, text="", font=("Segoe UI", 9), bg=BG, fg=MUTED, anchor="w",
                                  justify="left")
        self.found_lbl.pack(fill="x")

        # Current status
        self._section(body, "CURRENTLY INSTALLED")
        self.installed_lbl = tk.Label(body, text="—", font=("Segoe UI Semibold", 11), bg=BG, fg=TEXT,
                                      anchor="w", justify="left")
        self.installed_lbl.pack(fill="x")
        self.note_lbl = tk.Label(body, text="", font=("Segoe UI", 9), bg=BG, fg=WARN, anchor="w",
                                 justify="left")

        # Presets
        self._section(body, "CHOOSE DIFFICULTY")
        self.cards = {}
        for p in (NORMAL, EASY, STORY):
            c = PresetCard(body, p, self.preset_var, s, self.on_preset_change)
            c.pack(fill="x", pady=(0, int(8 * s)))
            self.cards[p.key] = c

        # Action row
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill="x", side="bottom")
        self.progress = ProgressBar(bottom, height=int(6 * s))
        self.progress.pack(fill="x", pady=(int(6 * s), int(6 * s)))
        act = tk.Frame(bottom, bg=BG)
        act.pack(fill="x")
        self.msg_lbl = tk.Label(act, text="", font=("Segoe UI", 9), bg=BG, fg=MUTED, anchor="w",
                                justify="left")
        self.msg_lbl.pack(side="left", fill="x", expand=True)
        self.apply_btn = tk.Button(act, text="Apply", font=("Segoe UI Semibold", 11), bg=ACCENT, fg="white",
                                   activebackground=ACCENT_DARK, activeforeground="white", relief="flat",
                                   bd=0, padx=int(22 * s), pady=int(6 * s), cursor="hand2",
                                   command=self.apply, disabledforeground="#e0d6ee")
        self.apply_btn.pack(side="right")
        links = tk.Frame(bottom, bg=BG)
        links.pack(fill="x", pady=(int(8 * s), 0))
        self._link(links, "Open game's Paks folder", self.open_paks)
        self._link(links, "Open log folder", lambda: os.startfile(appdata.data_dir()))
        tk.Label(links, text="Keep the game closed while applying.", font=("Segoe UI", 8),
                 bg=BG, fg=MUTED).pack(side="right")
        self.path_font = tkfont.Font(font=self.path_lbl.cget("font"))
        self.path_text = ""
        root.bind("<Configure>", self._on_resize)
        self._apply_widths()
        self.on_preset_change()

    def set_note(self, text, color=WARN):
        """Show a note under the installed status, or hide the line entirely when empty."""
        self.note_lbl.configure(text=text, fg=color)
        if text:
            self.note_lbl.pack(fill="x", after=self.installed_lbl)
        else:
            self.note_lbl.pack_forget()

    def _section(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI Semibold", 8), bg=BG, fg=MUTED, anchor="w") \
            .pack(fill="x", pady=(int(10 * self.scale), int(3 * self.scale)))

    def _link(self, parent, text, cmd):
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 9, "underline"), bg=BG, fg=ACCENT, cursor="hand2")
        lbl.pack(side="left", padx=(0, int(14 * self.scale)))
        lbl.bind("<Button-1>", lambda e: cmd())

    def _on_resize(self, event):
        if event.widget is self.root:
            w = max(int(400 * self.scale), event.width - 2 * int(18 * self.scale))
            if abs(w - self.content_w) > 2:
                self.content_w = w
                self._apply_widths()

    def _apply_widths(self):
        """Wrap long text to the window width so it never pushes the window wider."""
        s, w = self.scale, self.content_w
        self.installed_lbl.configure(wraplength=w)
        self.note_lbl.configure(wraplength=w)
        self.found_lbl.configure(wraplength=w)
        self.msg_lbl.configure(wraplength=w - int(190 * s))
        for c in self.cards.values():
            for lbl in c.lines + [c.tag]:
                lbl.configure(wraplength=w - int(70 * s))
        self._show_path()

    def _show_path(self):
        self.path_lbl.configure(text=_elide_middle(self.path_text, self.path_font,
                                                   self.content_w - int(120 * self.scale)))

    # ------------------------------------------------------------ game folder
    def detect_game(self):
        remembered = appdata.load_settings().get("game_dir")
        path, how = gamedetect.auto_detect(remembered)
        if path:
            self.set_game_dir(path, f"Found automatically ({how}).")
        else:
            self.set_game_dir(None, None)

    def browse(self):
        start = self.game_dir or os.path.expanduser("~")
        chosen = filedialog.askdirectory(parent=self.root, initialdir=start,
                                         title="Select the Queen's Domain install folder")
        if not chosen:
            return
        path = gamedetect.normalize_game_dir(chosen)
        if not path:
            messagebox.showerror(APP_NAME,
                                 "That folder doesn't contain Queen's Domain.\n\n"
                                 "Pick the game's install folder - the one with QueensDomain.exe in it. "
                                 "In Steam: right-click the game > Manage > Browse local files.",
                                 parent=self.root)
            return
        self.set_game_dir(path, "Chosen by you.")

    def set_game_dir(self, path, how):
        self.game_dir = path
        if path:
            appdata.save_settings(game_dir=path)
            self.path_text = path
            self._show_path()
            self.path_lbl.configure(fg=TEXT)
            self.found_lbl.configure(text="✔ " + how, fg=OK)
            log.info("Game folder: %s (%s)", path, how)
        else:
            self.path_text = "Queen's Domain wasn't found automatically."
            self._show_path()
            self.path_lbl.configure(fg=ERR)
            self.found_lbl.configure(text="Click Browse… and select the game's install folder "
                                          "(Steam: right-click the game > Manage > Browse local files).",
                                     fg=MUTED)
        self.refresh_status()

    def refresh_status(self):
        self.status = None
        for c in self.cards.values():
            c.set_installed(False)
        if not self.game_dir:
            self.installed_lbl.configure(text="—")
            self.set_note("")
            self.on_preset_change()
            return
        try:
            st = installer.get_status(self.game_dir)
        except (ModError, OSError) as e:
            self.installed_lbl.configure(text="Unknown")
            self.set_note(str(e), ERR)
            return
        self.status = st
        self.installed_lbl.configure(text=st.describe(), fg=ERR if st.problem else TEXT)
        if st.preset in self.cards and not st.problem:
            self.cards[st.preset].set_installed(True)
            if st.preset != NORMAL.key:
                self.preset_var.set(st.preset)
        notes = []
        if st.legacy_paks:
            notes.append("Applying any preset removes these older paks (Easy and Story replace them "
                         "with this mod's single file).")
        if st.game_updated:
            notes.append("⚠ The game was updated since this was applied. Click Apply again to refresh the mod.")
        if st.other_mods:
            notes.append("Other mods in the Paks folder (left untouched): " + ", ".join(st.other_mods))
        self.set_note("\n".join(notes))
        self.on_preset_change()

    def open_paks(self):
        if self.game_dir:
            os.startfile(gamedetect.paks_dir(self.game_dir))
        else:
            messagebox.showinfo(APP_NAME, "Choose the game folder first.", parent=self.root)

    # ------------------------------------------------------------------ apply
    def on_preset_change(self):
        p = PRESETS[self.preset_var.get()]
        if p.is_vanilla:
            self.apply_btn.configure(text="Restore Normal")
        else:
            self.apply_btn.configure(text=f"Apply {p.title}")
        busy = self.worker is not None
        self.apply_btn.configure(state="normal" if self.game_dir and not busy else "disabled",
                                 bg=ACCENT if self.game_dir and not busy else "#a99bbb")

    def _set_busy(self, busy):
        self.browse_btn.configure(state="disabled" if busy else "normal")
        for c in self.cards.values():
            c.set_enabled(not busy)
        self.on_preset_change()

    def apply(self):
        if self.worker or not self.game_dir:
            return
        if procs.game_running(self.game_dir):
            messagebox.showwarning(APP_NAME, "Queen's Domain is running.\n\nPlease quit the game completely "
                                   "(the game keeps its files locked while it runs), then click Apply again.",
                                   parent=self.root)
            return
        key = self.preset_var.get()
        self.progress.set(0)
        self.msg_lbl.configure(text="Starting…", fg=MUTED)
        self.worker = threading.Thread(target=self._work, args=(self.game_dir, key), daemon=True)
        self._set_busy(True)
        self.worker.start()
        self.root.after(50, self._poll)

    def _work(self, game_dir, key):
        def progress(fraction, message):
            self.events.put(("progress", fraction, message))
        try:
            res = installer.apply_preset(game_dir, key, progress)
            self.events.put(("done", res))
        except ModError as e:
            self.events.put(("error", e))
        except Exception as e:  # never leave the window stuck
            log.exception("Unexpected error while applying")
            self.events.put(("error", e))

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "progress":
                    self.progress.set(ev[1])
                    self.msg_lbl.configure(text=ev[2])
                elif ev[0] == "done":
                    self._finished(ev[1], None)
                    return
                elif ev[0] == "error":
                    self._finished(None, ev[1])
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def _finished(self, res, err):
        self.worker = None
        self._set_busy(False)
        self.refresh_status()
        if err is None:
            self.progress.set(1.0)
            p = PRESETS[res["preset"]]
            if p.is_vanilla:
                text = "✔ Normal restored - the mod is uninstalled."
            else:
                text = (f"✔ {p.title} applied and verified in {res['seconds']:.1f} s. "
                        "Start the game to play!")
            self.msg_lbl.configure(text=text, fg=OK)
            return
        self.progress.set(0)
        if isinstance(err, GameRunningError):
            self.msg_lbl.configure(text="Close the game, then try again.", fg=WARN)
            messagebox.showwarning(APP_NAME, str(err), parent=self.root)
        elif isinstance(err, ModError):
            self.msg_lbl.configure(text="Nothing was changed.", fg=ERR)
            messagebox.showerror(APP_NAME, f"{err}\n\nYour game files were not changed.", parent=self.root)
        else:
            self.msg_lbl.configure(text="Something went wrong.", fg=ERR)
            messagebox.showerror(APP_NAME, f"Something unexpected went wrong:\n{err}\n\n"
                                 f"Details are in the log:\n{appdata.log_path()}", parent=self.root)


def _started_minimized():
    """True if Windows asked us to start minimized (e.g. a shortcut set to "Run: Minimized")."""
    try:
        import ctypes
        from ctypes import wintypes

        class STARTUPINFOW(ctypes.Structure):
            _fields_ = ([("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                         ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR)]
                        + [(n, wintypes.DWORD) for n in ("dwX", "dwY", "dwXSize", "dwYSize", "dwXCountChars",
                                                         "dwYCountChars", "dwFillAttribute", "dwFlags")]
                        + [("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                           ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                           ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)])
        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        ctypes.windll.kernel32.GetStartupInfoW(ctypes.byref(si))
        return bool(si.dwFlags & 1) and si.wShowWindow in (2, 6, 7)  # STARTF_USESHOWWINDOW + a minimized mode
    except Exception:
        return False


def run():
    _enable_dpi_awareness()
    root = tk.Tk()
    if _started_minimized():
        root.iconify()
    App(root)
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 3)
    root.geometry(f"+{x}+{y}")
    root.mainloop()
    return 0
