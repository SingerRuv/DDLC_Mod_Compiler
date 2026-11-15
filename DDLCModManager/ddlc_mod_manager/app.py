"""DDLC Mod Manager main window."""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import devtools, icons, theme
from .compiler_tab import CompilerTab
from .config import APP, load_theme, migrate_legacy_data, resource_path, save_theme
from .launcher_tab import LauncherTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self._konami = devtools.Konami()
        self._dev_mode = False
        self._dev_job = None
        self._dev_snapshot = None
        self._dev_pending = False
        self._dev_relaunching = False
        self._supervised = os.environ.get(devtools.SUPERVISED_ENV) == "1"
        self._source_available = devtools.source_available()
        migrate_legacy_data()
        self.dark = load_theme()
        self.palette = theme.apply(self, self.dark)
        try:
            if sys.platform == "win32":
                icono = resource_path("DDLC.ico")
                if icono.is_file():
                    self.iconbitmap(default=str(icono))
            else:
                icono = resource_path("icon.png")
                if icono.is_file():
                    self._icono = tk.PhotoImage(file=str(icono))
                    self.iconphoto(True, self._icono)
        except Exception:
            pass
        self.title(APP)
        self.geometry("800x500")
        self.resizable(False, False)

        self.header = tk.Frame(self, bg=self.palette["header"], height=42)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.title_label = ttk.Label(self.header, text=APP,
                                     style="Title.TLabel")
        self.title_label.pack(side="left", padx=(14, 0), pady=9)
        self.dev_badge = tk.Label(
            self.header, text="DEV", bg=self.palette["accent"], fg="#ffffff",
            font=("Segoe UI", 8, "bold"), padx=8, pady=2)
        self.theme_button = tk.Button(
            self.header, text="Light" if self.dark else "Dark",
            command=self._toggle_theme,
            image=icons.get_icon("sun" if self.dark else "moon", self.dark),
            compound="left", relief="flat", bd=0, highlightthickness=0,
            bg=self.palette["header"], fg=self.palette["text"],
            activebackground=self.palette["button_active"],
            activeforeground=self.palette["text"],
            font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2")
        self.theme_button.pack(side="right", padx=(0, 12), pady=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.launcher = LauncherTab(self.notebook, dark=self.dark)
        self.compiler = CompilerTab(self.notebook, on_built=self._on_built,
                                    dark=self.dark)
        self.notebook.add(self.launcher, text="Launcher")
        self.notebook.add(self.compiler, text="Compiler")
        self.notebook.select(self.launcher)
        self._tab_icons = []
        self._update_tab_icons()
        self.bind_all("<KeyPress>", self._on_key, add="+")
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        if os.environ.get(devtools.DEV_ENV) == "1":
            self._set_developer_mode(True)

    def _update_tab_icons(self):
        self._tab_icons = [
            icons.get_icon("launcher", self.dark),
            icons.get_icon("compiler", self.dark),
        ]
        for index, image in enumerate(self._tab_icons):
            self.notebook.tab(index, image=image, compound="left")

    def _on_key(self, event):
        if self._konami.feed(event.keysym):
            self._set_developer_mode(not self._dev_mode)

    def _set_developer_mode(self, enabled):
        enabled = bool(enabled)
        if enabled == self._dev_mode:
            return
        self._dev_mode = enabled
        if not enabled:
            self.dev_badge.pack_forget()
            self._stop_dev_watcher()
            return
        self.dev_badge.pack(side="left", padx=(10, 0), pady=10)
        if not self._source_available:
            messagebox.showinfo(
                APP, "Developer Mode active.\n"
                     "Live Reload is available only when running from source.")
            return
        if self._supervised:
            return
        self._dev_snapshot = devtools.snapshot()
        self._dev_pending = False
        self._schedule_dev_poll()

    def _schedule_dev_poll(self):
        if self._dev_job is not None:
            self.after_cancel(self._dev_job)
        self._dev_job = self.after(500, self._dev_poll)

    def _stop_dev_watcher(self):
        if self._dev_job is not None:
            self.after_cancel(self._dev_job)
            self._dev_job = None
        self._dev_snapshot = None
        self._dev_pending = False

    def _dev_poll(self):
        self._dev_job = None
        if not self._dev_mode or self._supervised or not self._source_available:
            return
        current = devtools.snapshot()
        if self._dev_pending or current != self._dev_snapshot:
            self._dev_snapshot = current
            if self.compiler.is_building():
                self._dev_pending = True
                self._dev_job = self.after(1000, self._dev_poll)
                return
            self._dev_pending = False
            self._relaunch_for_dev()
            return
        self._dev_job = self.after(500, self._dev_poll)

    def _relaunch_for_dev(self):
        if self._dev_relaunching:
            return
        self._dev_relaunching = True
        env = os.environ.copy()
        env[devtools.DEV_ENV] = "1"
        env.pop(devtools.SUPERVISED_ENV, None)
        try:
            process = subprocess.Popen(
                [sys.executable, str(devtools.ENTRY)],
                cwd=str(devtools.ROOT), env=env)
        except OSError as exc:
            self._dev_relaunching = False
            messagebox.showerror(APP, "Live Reload failed:\n%s" % exc)
            self._schedule_dev_poll()
            return
        self.after(1500, lambda: self._finish_dev_relaunch(process))

    def _finish_dev_relaunch(self, process):
        self._dev_relaunching = False
        if process.poll() is None:
            self._stop_dev_watcher()
            self.destroy()
            return
        messagebox.showerror(
            APP, "Live Reload failed: the new process exited.")
        self._dev_snapshot = devtools.snapshot()
        self._dev_pending = False
        if self._dev_mode:
            self._schedule_dev_poll()

    def _toggle_theme(self):
        self.dark = not self.dark
        save_theme(self.dark)
        self.palette = theme.apply(self, self.dark)
        self.configure(bg=self.palette["bg"])
        self.header.configure(bg=self.palette["header"])
        self.theme_button.configure(
            text="Light" if self.dark else "Dark",
            image=icons.get_icon("sun" if self.dark else "moon", self.dark),
            bg=self.palette["header"], fg=self.palette["text"],
            activebackground=self.palette["button_active"],
            activeforeground=self.palette["text"])
        self.dev_badge.configure(bg=self.palette["accent"], fg="#ffffff")
        self.launcher.apply_theme(self.dark)
        self.compiler.apply_theme(self.dark)
        self._update_tab_icons()

    def _on_built(self, path):
        self.launcher.add_build(path)

    def _cerrar(self):
        if self.compiler.is_building():
            if not messagebox.askyesno(
                    APP, "A build is in progress.\nCancel and exit?"):
                return
            self.compiler.cancel_for_close()
            self._cerrar_espera()
        else:
            self._stop_dev_watcher()
            self.destroy()

    def _cerrar_espera(self):
        if self.compiler.is_building():
            self.after(200, self._cerrar_espera)
        else:
            self._stop_dev_watcher()
            self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
