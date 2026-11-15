"""Launcher tab."""
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import APP, MODS_ROOT, ensure_mods_root, resource_path
from .library import (entry_from_path, load_state, save_state, scan_roots)
from .platforms import open_launcher, open_path


class LauncherTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.status = tk.StringVar(value="No mods loaded.")
        self._entries = []
        self._external_roots = []
        self._extra_paths = []
        self._images = []
        self._scan_cancel = threading.Event()
        self._scan_queue = queue.Queue()
        self._scan_thread = None
        self._action_buttons = []
        self._build_ui()
        self._external_roots, self._extra_paths = load_state()
        self.status.set("Scanning mods... Please wait.")
        self.after(100, self.start_scan)

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        ttk.Button(top, text="Open mods folder",
                   command=self._open_mods_root).pack(side="left")
        self.scan_btn = ttk.Button(top, text="Rescan",
                                   command=self.start_scan)
        self.scan_btn.pack(side="left", padx=(8, 0))
        add_btn = ttk.Button(top, text="Add folder...",
                             command=self._add_folder)
        add_btn.pack(side="left", padx=(8, 0))
        import_btn = ttk.Button(top, text="Import mod...",
                                command=self._import_mod)
        import_btn.pack(side="left", padx=(8, 0))
        self._action_buttons = [add_btn, import_btn]
        ttk.Label(self, text="Mods folder: %s" % MODS_ROOT).pack(
            anchor="w", pady=(0, 4))
        ttk.Label(self, textvariable=self.status).pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, highlightthickness=0)
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

    def is_scanning(self):
        return bool(self._scan_thread and self._scan_thread.is_alive())

    def start_scan(self):
        if self.is_scanning():
            return
        self._scan_cancel.clear()
        self.status.set("Scanning mods... Please wait.")
        self.scan_btn.configure(text="Cancel scan", command=self.cancel_scan)
        for button in self._action_buttons:
            button.configure(state="disabled")
        roots = [str(MODS_ROOT)] + list(self._external_roots)
        extra = list(self._extra_paths)
        self._scan_thread = threading.Thread(
            target=self._scan_worker, args=(roots, extra), daemon=True)
        self._scan_thread.start()
        self.after(100, self._poll_scan)

    def cancel_scan(self):
        if self.is_scanning():
            self._scan_cancel.set()
            self.status.set("Cancelling scan...")

    def rescan(self):
        self.start_scan()

    def _scan_worker(self, roots, extra):
        try:
            entries = scan_roots(roots, self._scan_cancel)
            if not self._scan_cancel.is_set():
                for path in extra:
                    if self._scan_cancel.is_set():
                        break
                    entry = entry_from_path(path)
                    if entry:
                        entries.append(entry)
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
            self.status.set("%d runnable mods found." % len(self._entries))
        elif kind == "cancelled":
            self.status.set("Scan cancelled.")
        else:
            self.status.set("Scan failed: %s" % payload)
        self._finish_scan()

    def _finish_scan(self):
        self.scan_btn.configure(text="Rescan", command=self.start_scan)
        for button in self._action_buttons:
            button.configure(state="normal")

    def _apply_entries(self, entries):
        by_path = {entry["path"]: entry for entry in entries}
        for path in self._extra_paths:
            entry = entry_from_path(path)
            if entry:
                by_path[entry["path"]] = entry
        self._entries = sorted(by_path.values(),
                               key=lambda e: e["name"].casefold())
        self._extra_paths = [entry["path"] for entry in self._entries]
        try:
            save_state(self._external_roots, self._entries)
        except OSError as exc:
            self.status.set("Could not save launcher state: %s" % exc)
        self._render()

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
            self._apply_entries(self._entries)

    def _render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        self._images.clear()
        self.cards.columnconfigure(0, weight=1)
        self.cards.columnconfigure(1, weight=1)
        if not self._entries:
            ttk.Label(
                self.cards,
                text="No runnable mods loaded.\n"
                     "Build a mod or import one to get started.",
                justify="center").grid(row=0, column=0, columnspan=2,
                                       pady=40, sticky="n")
            return
        for i, entry in enumerate(self._entries):
            self._card(entry, i // 2, i % 2)

    def _card(self, entry, row, col):
        card = ttk.Frame(self.cards, padding=8, relief="groove")
        card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        card.columnconfigure(1, weight=1)

        image = self._logo(entry)
        logo = ttk.Label(card, image=image) if image else ttk.Label(
            card, text="DDLC")
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 8), sticky="n")

        ttk.Label(card, text=entry["name"], font=("Segoe UI", 10, "bold"),
                  wraplength=210).grid(row=0, column=1, sticky="w")
        ttk.Label(card, text=entry["kind"], foreground="#555").grid(
            row=1, column=1, sticky="w")

        buttons = ttk.Frame(card)
        buttons.grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 0))
        ttk.Button(buttons, text="Launch",
                   command=lambda e=entry: self._launch(e)).pack(
            side="top", fill="x")
        ttk.Button(buttons, text="Open folder",
                   command=lambda e=entry: self._open_folder(e)).pack(
            side="top", fill="x", pady=(4, 0))

    def _logo(self, entry):
        candidates = [entry.get("logo"), resource_path("icon.png")]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if not path.is_file():
                continue
            try:
                image = tk.PhotoImage(file=str(path))
                factor = max(1, max(image.width(), image.height()) // 56)
                if factor > 1:
                    image = image.subsample(factor)
                self._images.append(image)
                return image
            except Exception:
                continue
        return None

    def _launch(self, entry):
        try:
            open_launcher(Path(entry["launcher"]), cwd=Path(entry["path"]))
        except Exception as exc:
            messagebox.showerror(APP, "Could not launch the mod:\n%s" % exc)

    def _open_folder(self, entry):
        try:
            open_path(entry["path"])
        except Exception as exc:
            messagebox.showerror(APP, "Could not open the folder:\n%s" % exc)
