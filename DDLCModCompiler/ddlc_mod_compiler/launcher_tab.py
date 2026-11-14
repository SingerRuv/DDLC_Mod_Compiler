"""Launcher tab."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import APP, resource_path
from .library import (entries_from_paths, entry_from_path, load_state,
                      save_state, scan_mods)
from .platforms import open_launcher, open_path


class LauncherTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.root_path = tk.StringVar()
        self.status = tk.StringVar(value="No mods loaded.")
        self._entries = []
        self._images = []
        self._build_ui()
        root, paths = load_state()
        self.root_path.set(root)
        self._entries = entries_from_paths(paths)
        self._render()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Choose mods folder...",
                   command=self._choose_folder).pack(side="left")
        ttk.Button(top, text="Rescan", command=self.rescan).pack(
            side="left", padx=(8, 0))
        ttk.Label(top, textvariable=self.status).pack(
            side="left", padx=(12, 0))

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

    def _choose_folder(self):
        path = filedialog.askdirectory(title="Mods folder")
        if path:
            self.root_path.set(path)
            self.rescan()

    def rescan(self):
        root = self.root_path.get().strip()
        if not root:
            messagebox.showwarning(APP, "Choose a mods folder first.")
            return
        self._entries = scan_mods(root)
        save_state(root, self._entries)
        self._render()
        self.status.set("%d runnable mods found." % len(self._entries))

    def add_build(self, path):
        entry = entry_from_path(path)
        if not entry:
            return
        replaced = False
        for i, old in enumerate(self._entries):
            if old["path"] == entry["path"]:
                self._entries[i] = entry
                replaced = True
                break
        if not replaced:
            self._entries.append(entry)
        self._entries.sort(key=lambda e: e["name"].casefold())
        save_state(self.root_path.get().strip(), self._entries)
        self._render()

    def _render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        self._images.clear()
        self.cards.columnconfigure(0, weight=1)
        self.cards.columnconfigure(1, weight=1)
        if not self._entries:
            ttk.Label(
                self.cards,
                text="No runnable mods loaded.\nChoose a mods folder to scan.",
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
