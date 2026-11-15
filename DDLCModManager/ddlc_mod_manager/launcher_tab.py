"""Launcher tab."""
import queue
import threading
from collections import OrderedDict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from . import icons, theme
from .config import APP, MODS_ROOT, ensure_mods_root
from .library import (entry_from_path, filter_entries, load_state, save_state,
                      scan_roots, sort_entries)
from .platforms import (find_launcher, open_launcher, open_path,
                        platform_name)

CARD_COLUMNS = 3
CARD_WIDTH = 230
CARD_LOGO = 150
CARD_HEIGHT = CARD_LOGO + 185
IMAGE_CACHE_LIMIT = 128
IMAGE_CACHE_BYTES = 32 * 1024 * 1024


def _image_cache_key(path, logo_size=CARD_LOGO):
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return (str(path), stat.st_mtime_ns, stat.st_size, logo_size)


def _image_bytes(image):
    try:
        return max(1, int(image.width()) * int(image.height()) * 4)
    except Exception:
        return 1


class LauncherTab(ttk.Frame):
    def __init__(self, master, dark=False):
        super().__init__(master, padding=12)
        self.dark = dark
        self.platform = platform_name()
        self.status = tk.StringVar(value="No mods loaded.")
        self._entries = []
        self._all_entries = []
        self.search_var = tk.StringVar()
        self.runtime_filter = tk.StringVar(value="All")
        self.sort_mode = tk.StringVar(value="Name A-Z")
        self._view_job = None
        self._external_roots = []
        self._extra_paths = []
        self._images = []
        self._image_cache = OrderedDict()
        self._image_cache_bytes = 0
        self._active_image_keys = set()
        self._icon_buttons = []
        self._scan_cancel = threading.Event()
        self._scan_queue = queue.Queue()
        self._scan_thread = None
        self._action_buttons = []
        self._build_ui()
        self._external_roots, self._extra_paths = load_state()
        self.status.set("Scanning %s mods... Please wait." % self.platform)
        self.after(100, self.start_scan)

    def _tool_button(self, parent, text, icon_name, command):
        button = ttk.Button(
            parent, text=text, image=icons.get_icon(icon_name, self.dark),
            compound="left", command=command)
        self._icon_buttons.append((button, icon_name))
        return button

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        self._tool_button(top, "Open mods folder", "folder",
                          self._open_mods_root).pack(side="left")
        self.scan_btn = self._tool_button(
            top, "Rescan", "refresh", self.start_scan)
        self.scan_btn.pack(side="left", padx=(8, 0))
        add_btn = self._tool_button(top, "Add folder...", "add-folder",
                                    self._add_folder)
        add_btn.pack(side="left", padx=(8, 0))
        import_btn = self._tool_button(top, "Import mod...", "import",
                                       self._import_mod)
        import_btn.pack(side="left", padx=(8, 0))
        self._action_buttons = [add_btn, import_btn]
        ttk.Label(self, text="Mods folder: %s" % MODS_ROOT,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(self, text="Platform: %s" % self.platform,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 4))

        filters = ttk.Frame(self)
        filters.pack(fill="x", pady=(0, 4))
        ttk.Label(filters, text="Search:").pack(side="left")
        ttk.Entry(filters, textvariable=self.search_var, width=28).pack(
            side="left", padx=(4, 12))
        ttk.Label(filters, text="Filter:").pack(side="left")
        ttk.Combobox(
            filters, textvariable=self.runtime_filter, state="readonly",
            width=12,
            values=("All", "Ren'Py 6", "Ren'Py 7", "Ren'Py 8",
                    "DDLC build", "Other")).pack(side="left", padx=(4, 12))
        ttk.Label(filters, text="Sort:").pack(side="left")
        ttk.Combobox(
            filters, textvariable=self.sort_mode, state="readonly", width=12,
            values=("Name A-Z", "Name Z-A", "Newest first",
                    "Oldest first")).pack(side="left", padx=(4, 0))
        self.search_var.trace_add("write", lambda *_: self._schedule_view())
        self.runtime_filter.trace_add("write", lambda *_: self._schedule_view())
        self.sort_mode.trace_add("write", lambda *_: self._schedule_view())

        ttk.Label(self, textvariable=self.status).pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, highlightthickness=0,
                                bg=theme.palette(self.dark)["bg"])
        scroll = ttk.Scrollbar(body, orient="vertical",
                               command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.cards = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.cards,
                                                 anchor="nw")
        self.cards.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window, width=e.width))

    def _schedule_view(self):
        if self._view_job:
            self.after_cancel(self._view_job)
        self._view_job = self.after(120, self._apply_view)

    def _apply_view(self):
        self._view_job = None
        self._entries = sort_entries(
            filter_entries(self._all_entries, self.search_var.get(),
                           self.runtime_filter.get()),
            self.sort_mode.get())
        self._render()
        total = len(self._all_entries)
        shown = len(self._entries)
        if not total:
            self.status.set("No runnable mods loaded.")
        elif shown == total:
            self.status.set("%d runnable %s found." % (
                total, "mod" if total == 1 else "mods"))
        else:
            self.status.set("%d of %d runnable mods shown." % (shown, total))

    def apply_theme(self, dark):
        self.dark = dark
        self.canvas.configure(bg=theme.palette(dark)["bg"])
        for button, icon_name in self._icon_buttons:
            button.configure(image=icons.get_icon(icon_name, dark))
        self._apply_view()

    def is_scanning(self):
        return bool(self._scan_thread and self._scan_thread.is_alive())

    def start_scan(self):
        if self.is_scanning():
            return
        self._scan_cancel.clear()
        self.status.set("Scanning %s mods... Please wait." % self.platform)
        self.scan_btn.configure(
            text="Cancel scan", command=self.cancel_scan,
            image=icons.get_icon("cancel", self.dark))
        for button in self._action_buttons:
            button.configure(state="disabled")
        roots = [str(MODS_ROOT)] + list(self._external_roots)
        self._scan_thread = threading.Thread(
            target=self._scan_worker, args=(roots,), daemon=True)
        self._scan_thread.start()
        self.after(100, self._poll_scan)

    def cancel_scan(self):
        if self.is_scanning():
            self._scan_cancel.set()
            self.status.set("Cancelling scan...")

    def _scan_worker(self, roots):
        try:
            entries = scan_roots(roots, self._scan_cancel)
            if self._scan_cancel.is_set():
                self._scan_queue.put(("cancelled", None))
            else:
                self._scan_queue.put(("done", entries))
        except Exception as exc:
            self._scan_queue.put(("error", str(exc)))

    def _poll_scan(self):
        try:
            kind, payload = self._scan_queue.get_nowait()
        except queue.Empty:
            if self.is_scanning():
                self.after(100, self._poll_scan)
            else:
                self._finish_scan()
            return
        self._scan_thread = None
        if kind == "done":
            self._apply_entries(payload)
        elif kind == "cancelled":
            self.status.set("Scan cancelled.")
        else:
            self.status.set("Scan failed: %s" % payload)
        self._finish_scan()

    def _finish_scan(self):
        self.scan_btn.configure(
            text="Rescan", command=self.start_scan,
            image=icons.get_icon("refresh", self.dark))
        for button in self._action_buttons:
            button.configure(state="normal")

    def _apply_entries(self, entries):
        by_path = {entry["path"]: entry for entry in entries}
        for path in self._extra_paths:
            if path in by_path:
                continue
            entry = entry_from_path(path)
            if entry:
                by_path[entry["path"]] = entry
        self._all_entries = list(by_path.values())
        self._extra_paths = [entry["path"] for entry in self._all_entries]
        try:
            save_state(self._external_roots, self._all_entries)
        except OSError as exc:
            self.status.set("Could not save launcher state: %s" % exc)
        self._apply_view()

    def _open_mods_root(self):
        ensure_mods_root()
        open_path(str(MODS_ROOT))

    def _add_folder(self):
        path = filedialog.askdirectory(title="Additional mods folder")
        if not path:
            return
        resolved = str(Path(path).resolve())
        if resolved not in self._external_roots:
            self._external_roots.append(resolved)
        self.start_scan()

    def _import_mod(self):
        path = filedialog.askdirectory(title="Import mod folder")
        if not path:
            return
        entry = entry_from_path(path)
        if entry is None:
            messagebox.showwarning(
                APP, "That folder has no runnable mod launcher.")
            return
        if entry["path"] not in self._extra_paths:
            self._extra_paths.append(entry["path"])
        self.start_scan()

    def add_build(self, path):
        entry = entry_from_path(path)
        if not entry:
            return
        if entry["path"] not in self._extra_paths:
            self._extra_paths.append(entry["path"])
        if not self.is_scanning():
            self._apply_entries(self._all_entries)

    def _render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        self._images.clear()
        self._active_image_keys.clear()
        self.cards.columnconfigure(0, weight=0, minsize=CARD_WIDTH)
        self.cards.columnconfigure(1, weight=0, minsize=CARD_WIDTH)
        self.cards.columnconfigure(2, weight=0, minsize=CARD_WIDTH)
        if not self._entries:
            text = ("No mods match the current filters."
                    if self._all_entries else
                    "No runnable mods loaded.\n"
                    "Build a mod or import one to get started.")
            ttk.Label(
                self.cards, text=text, justify="center").grid(
                row=0, column=0, columnspan=CARD_COLUMNS,
                pady=40, sticky="n")
            return
        for i, entry in enumerate(self._entries):
            self._card(entry, i // CARD_COLUMNS, i % CARD_COLUMNS)

    def _card(self, entry, row, col):
        card = ttk.Frame(self.cards, padding=6, style="Card.TFrame",
                         width=CARD_WIDTH, height=CARD_HEIGHT)
        card.grid(row=row, column=col, sticky="nw", padx=4, pady=4)
        card.grid_propagate(False)
        card.columnconfigure(0, weight=1)

        image = self._logo(entry)
        if image:
            logo = ttk.Label(card, image=image, style="Card.TLabel")
        else:
            initial = (entry["name"][:1] or "?").upper()
            logo = tk.Label(
                card, text=initial, bg=theme.palette(self.dark)["accent"],
                fg="#ffffff", font=("Segoe UI", 16, "bold"), width=3,
                height=2, relief="flat", bd=0)
        logo.grid(row=0, column=0, pady=(0, 4), sticky="n")

        ttk.Label(card, text=entry["name"], font=("Segoe UI", 10, "bold"),
                  style="Card.TLabel", wraplength=200).grid(
            row=1, column=0, sticky="w")
        ttk.Label(card, text=entry["kind"], style="CardMuted.TLabel").grid(
            row=2, column=0, sticky="w")

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Launch",
                   image=icons.get_icon("play", self.dark),
                   compound="left",
                   command=lambda e=entry: self._launch(e)).grid(
            row=0, column=0, sticky="ew")
        ttk.Button(buttons, text="Open folder",
                   image=icons.get_icon("open-folder", self.dark),
                   compound="left",
                   command=lambda e=entry: self._open_folder(e)).grid(
            row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(buttons, text="Rename...",
                   command=lambda e=entry: self._rename_mod(e)).grid(
            row=2, column=0, sticky="ew", pady=(4, 0))

    def _remember_image(self, key, image):
        if key is None:
            return
        self._image_cache[key] = image
        self._image_cache_bytes += _image_bytes(image)
        self._trim_image_cache()

    def _trim_image_cache(self):
        while (len(self._image_cache) > IMAGE_CACHE_LIMIT or
               self._image_cache_bytes > IMAGE_CACHE_BYTES):
            victim = next(
                (key for key in self._image_cache
                 if key not in self._active_image_keys), None)
            if victim is None:
                break
            image = self._image_cache.pop(victim)
            self._image_cache_bytes -= _image_bytes(image)

    def _logo(self, entry):
        candidates = [entry.get("logo")]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if not path.is_file():
                continue
            key = _image_cache_key(path)
            if key is not None:
                cached = self._image_cache.get(key)
                if cached is not None:
                    self._image_cache.move_to_end(key)
                    self._active_image_keys.add(key)
                    self._images.append(cached)
                    return cached
            try:
                if ImageTk is not None:
                    with Image.open(path) as source:
                        image_data = source.convert("RGBA")
                    image_data.thumbnail((CARD_LOGO, CARD_LOGO),
                                         Image.LANCZOS)
                    image = ImageTk.PhotoImage(image_data, master=self)
                else:
                    image = tk.PhotoImage(file=str(path))
                    factor = max(1, max(image.width(), image.height()) //
                                 CARD_LOGO)
                    if factor > 1:
                        image = image.subsample(factor)
                if key is not None:
                    self._active_image_keys.add(key)
                self._remember_image(key, image)
                self._images.append(image)
                return image
            except Exception:
                continue
        return None

    def _launch(self, entry):
        try:
            root = Path(entry["path"])
            launcher = find_launcher(root)
            if launcher is None:
                messagebox.showerror(
                    APP, "No %s launcher found for this mod." % self.platform)
                return
            entry["launcher"] = str(launcher)
            open_launcher(launcher, cwd=root)
        except Exception as exc:
            messagebox.showerror(APP, "Could not launch the mod:\n%s" % exc)

    def _open_folder(self, entry):
        try:
            open_path(entry["path"])
        except Exception as exc:
            messagebox.showerror(APP, "Could not open the folder:\n%s" % exc)

    def _rename_mod(self, entry):
        old = Path(entry["path"])
        name = simpledialog.askstring(
            "Rename mod", "New folder name:", initialvalue=old.name,
            parent=self)
        if name is None:
            return
        name = name.strip()
        if (not name or name in (".", "..") or
                any(c in name for c in '\\/:*?"<>|')):
            messagebox.showwarning(APP, "Enter a valid folder name.")
            return
        target = old.with_name(name)
        if target == old:
            return
        if target.exists():
            messagebox.showerror(APP, "A folder with that name already exists.")
            return
        try:
            old.rename(target)
        except OSError as exc:
            messagebox.showerror(APP, "Could not rename the mod:\n%s" % exc)
            return
        old_path = str(old.resolve())
        new_path = str(target.resolve())
        self._all_entries = [
            e for e in self._all_entries if e["path"] != old_path]
        self._extra_paths = [
            new_path if path == old_path else path
            for path in self._extra_paths]
        self._apply_entries(self._all_entries)

