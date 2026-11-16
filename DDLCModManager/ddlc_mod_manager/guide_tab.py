"""Dynamic How to use tab."""
import tkinter as tk
from tkinter import ttk

from . import theme

BUILD_STEPS = (
    ("Select the DDLC base",
     "Choose a clean DDLC 1.1.1 base in the Compiler tab."),
    ("Choose the mod",
     "Select a mod folder or ZIP with Choose...; the mode is detected "
     "automatically."),
    ("Confirm the output",
     "The output is created under ~/DDLC Mods with the mod name."),
    ("Pick build options",
     "Include credits, create an optional ZIP, or open the game when done."),
    ("Build and launch",
     "Press Build, follow the progress, then open the mod from the Launcher."),
)

MANAGE_STEPS = (
    ("Open your mods folder",
     "Your builds live in ~/DDLC Mods. Use Open mods folder to get there."),
    ("Add or import mods",
     "Use Add folder... for another library or Import mod... for one build."),
    ("Find a mod",
     "Search by name and filter or sort the cards by runtime and date."),
    ("Launch or manage",
     "Use Launch, Open folder, or Rename... directly from each mod card."),
)


def mode_ready(mode):
    mode = str(mode or "").strip()
    return (bool(mode) and mode not in ("Mode: not detected",
                                        "Mode: not recognized") and
            "unsupported" not in mode)


def build_step_states(base, mod, mode, output, built=False, building=False):
    done = [
        bool(base),
        bool(mod) and mode_ready(mode),
        bool(output),
        bool(output),
        bool(built) and not building,
    ]
    if building:
        current = 4
    else:
        current = next((index for index, value in enumerate(done)
                        if not value), 4)
    return done, current


class GuideTab(ttk.Frame):
    def __init__(self, master, compiler=None, launcher=None, dark=False):
        super().__init__(master, padding=12)
        self._compiler = compiler
        self._launcher = launcher
        self.dark = dark
        self._section = "build"
        self._selected = None
        self._signature = None
        self._build_ui()
        self.apply_theme(dark)
        self.after(400, self._poll)

    def _build_ui(self):
        self._title = tk.Label(self, text="How to use", anchor="w",
                               font=("Segoe UI", 15, "bold"))
        self._title.pack(fill="x")
        self._subtitle = tk.Label(
            self, text="Follow the steps or jump to the part you need.",
            anchor="w", font=("Segoe UI", 9))
        self._subtitle.pack(fill="x", pady=(0, 8))

        sections = ttk.Frame(self)
        sections.pack(fill="x", pady=(0, 8))
        self._section_buttons = {}
        for key, label in (("build", "Build a mod"),
                           ("manage", "Manage mods")):
            button = tk.Button(
                sections, text=label, relief="flat", bd=0,
                highlightthickness=0, cursor="hand2", padx=12, pady=4,
                command=lambda value=key: self.set_section(value))
            button.pack(side="left", padx=(0, 8))
            self._section_buttons[key] = button

        self._status = tk.Label(self, text="", anchor="w",
                                font=("Segoe UI", 9))
        self._status.pack(fill="x", pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, minsize=210)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=0)

        self._steps = tk.Frame(body)
        self._steps.grid(row=0, column=0, sticky="new", padx=(0, 10))

        self._detail = tk.Frame(body, bd=0, highlightthickness=1)
        self._detail.grid(row=0, column=1, sticky="new")
        self._detail_title = tk.Label(
            self._detail, text="", anchor="w", justify="left",
            font=("Segoe UI", 11, "bold"), wraplength=470)
        self._detail_title.pack(fill="x", padx=12, pady=(12, 4))
        self._detail_body = tk.Label(
            self._detail, text="", anchor="nw", justify="left",
            font=("Segoe UI", 9), wraplength=470)
        self._detail_body.pack(fill="x", padx=12)
        self._detail_hint = tk.Label(
            self._detail, text="", anchor="w", justify="left",
            font=("Segoe UI", 8), wraplength=470)
        self._detail_hint.pack(fill="x", padx=12, pady=(4, 8))
        self._detail_button = ttk.Button(self._detail, text="Go to Compiler")
        self._detail_button.pack(anchor="e", padx=12, pady=(0, 12))

    def set_section(self, section):
        if section not in ("build", "manage"):
            return
        self._section = section
        self._selected = 0
        self._signature = None
        self._style_sections()
        self._render()

    def _style_sections(self):
        p = theme.palette(self.dark)
        for key, button in self._section_buttons.items():
            active = key == self._section
            button.configure(
                bg=p["accent"] if active else p["button"],
                fg="#ffffff" if active else p["text"],
                activebackground=p["accent"] if active else p["button_active"],
                activeforeground="#ffffff" if active else p["text"],
                font=("Segoe UI", 9, "bold") if active else ("Segoe UI", 9))

    def apply_theme(self, dark):
        self.dark = dark
        p = theme.palette(dark)
        self._title.configure(bg=p["bg"], fg=p["text"])
        self._subtitle.configure(bg=p["bg"], fg=p["muted"])
        self._status.configure(bg=p["bg"], fg=p["muted"])
        self._steps.configure(bg=p["bg"])
        self._detail.configure(bg=p["card"],
                               highlightbackground=p["border"])
        for widget in (self._detail_title, self._detail_body,
                       self._detail_hint):
            widget.configure(bg=p["card"], fg=p["text"])
        self._detail_hint.configure(fg=p["muted"])
        self._style_sections()
        self._signature = None
        self._render()

    def _compiler_state(self):
        if self._compiler is not None:
            return self._compiler.guide_state()
        return {"base": "", "mod": "", "mode": "Mode: not detected",
                "output": "", "built": False, "building": False}

    def _render(self):
        state = self._compiler_state()
        count = len(getattr(self._launcher, "_all_entries", []) or [])
        if self._section == "build":
            steps = BUILD_STEPS
            done, current = build_step_states(
                state["base"], state["mod"], state["mode"],
                state["output"], state["built"], state["building"])
            if state["building"]:
                status = "Building..."
            elif state["built"]:
                status = "Build complete. Open the Launcher."
            elif not state["base"]:
                status = "Next: select the DDLC base."
            elif not state["mod"]:
                status = "Next: choose a mod."
            elif not mode_ready(state["mode"]):
                status = "Review the selected mod before building."
            elif not state["output"]:
                status = "Next: confirm the output folder."
            else:
                status = "Next: build the mod."
            detail_button, detail_command = "Go to Compiler", self._compiler
        else:
            steps = MANAGE_STEPS
            done = [bool(count), bool(count), bool(count), False]
            current = 0 if not count else 3
            status = ("%d mods loaded. Select a mod to launch." % count
                      if count else "Open your mods folder to get started.")
            detail_button, detail_command = "Go to Launcher", self._launcher

        effective = self._selected if self._selected is not None else current
        effective = min(effective, len(steps) - 1)
        signature = (self._section, self.dark, tuple(done), current,
                     effective, count, state["mode"], state["built"],
                     state["building"])
        if signature == self._signature:
            return
        self._signature = signature
        p = theme.palette(self.dark)
        self._status.configure(text=status)

        for child in self._steps.winfo_children():
            child.destroy()
        for index, (title, _body) in enumerate(steps):
            active = index == effective
            bg = p["button"] if active else p["bg"]
            fg = p["accent"] if active else (
                p["muted"] if done[index] else p["text"])
            row = tk.Frame(self._steps, bg=bg, cursor="hand2")
            row.pack(fill="x", pady=(0, 4))
            marker = tk.Label(
                row, text="\u2713" if done[index] else str(index + 1),
                width=3, anchor="center", bg=bg, fg=fg,
                font=("Segoe UI", 9, "bold"))
            marker.pack(side="left", padx=(5, 2), pady=6)
            label = tk.Label(row, text=title, anchor="w", bg=bg, fg=fg,
                             font=("Segoe UI", 9))
            label.pack(side="left", fill="x", expand=True, padx=(0, 5),
                       pady=6)
            for widget in (row, marker, label):
                widget.bind("<Button-1>",
                            lambda _event, i=index: self._select_step(i))

        title, body = steps[effective]
        self._detail_title.configure(text=title)
        self._detail_body.configure(text=body)
        self._detail_hint.configure(
            text="Step %d of %d" % (effective + 1, len(steps)))
        self._detail_button.configure(text=detail_button)
        self._detail_button.configure(
            command=lambda widget=detail_command: self._open(widget))

    def _select_step(self, index):
        self._selected = index
        self._signature = None
        self._render()

    def _open(self, widget):
        if widget is not None:
            self.master.select(widget)

    def _poll(self):
        self._render()
        self.after(400, self._poll)
