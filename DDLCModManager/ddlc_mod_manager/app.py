"""DDLC Mod Manager main window."""
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import icons, theme
from .compiler_tab import CompilerTab
from .config import APP, load_theme, migrate_legacy_data, resource_path, save_theme
from .launcher_tab import LauncherTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
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
        self.geometry("900x500")
        self.minsize(760, 480)

        self.header = tk.Frame(self, bg=self.palette["header"], height=42)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.title_label = ttk.Label(self.header, text=APP,
                                     style="Title.TLabel")
        self.title_label.pack(side="left", padx=(14, 0), pady=9)
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
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _update_tab_icons(self):
        self._tab_icons = [
            icons.get_icon("launcher", self.dark),
            icons.get_icon("compiler", self.dark),
        ]
        for index, image in enumerate(self._tab_icons):
            self.notebook.tab(index, image=image, compound="left")

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
