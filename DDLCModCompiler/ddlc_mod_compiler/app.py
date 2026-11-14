"""DDLC Mod Compiler main window."""
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .compiler_tab import CompilerTab
from .config import APP, resource_path
from .launcher_tab import LauncherTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
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
        self.geometry("900x460")
        self.minsize(760, 440)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.launcher = LauncherTab(self.notebook)
        self.compiler = CompilerTab(self.notebook, on_built=self._on_built)
        self.notebook.add(self.launcher, text="Launcher")
        self.notebook.add(self.compiler, text="Compiler")
        self.notebook.select(self.launcher)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

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
            self.destroy()

    def _cerrar_espera(self):
        if self.compiler.is_building():
            self.after(200, self._cerrar_espera)
        else:
            self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
