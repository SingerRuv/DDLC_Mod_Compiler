"""Light/dark ttk styling for the application."""
from tkinter import ttk

LIGHT = {
    "bg": "#f3f4f6",
    "header": "#ffffff",
    "card": "#ffffff",
    "border": "#d7dbe2",
    "text": "#20252b",
    "muted": "#66707b",
    "entry": "#ffffff",
    "accent": "#b84d86",
    "button": "#eef0f3",
    "button_active": "#e2e5ea",
}

DARK = {
    "bg": "#1b2026",
    "header": "#151a1f",
    "card": "#252c34",
    "border": "#38434e",
    "text": "#e7eaf0",
    "muted": "#9aa7b4",
    "entry": "#14191e",
    "accent": "#d45a9a",
    "button": "#2b333c",
    "button_active": "#35404b",
}


def palette(dark):
    return DARK if dark else LIGHT


def _native_theme(style):
    names = style.theme_names()
    for name in ("vista", "aqua", "xpnative", "default", "clam"):
        if name in names:
            return name
    return "clam"


def apply(root, dark):
    style = ttk.Style(root)
    if dark:
        style.theme_use("clam")
    else:
        style.theme_use(_native_theme(style))
    p = palette(dark)

    style.configure("TButton", padding=(8, 4))
    style.configure("TNotebook.Tab", padding=(12, 6))
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"),
                    foreground=p["text"], background=p["header"])
    style.configure("Muted.TLabel", foreground=p["muted"],
                    background=p["bg"])
    style.configure("Card.TFrame", background=p["card"],
                    bordercolor=p["border"], relief="solid", borderwidth=1)
    style.configure("Card.TLabel", background=p["card"],
                    foreground=p["text"])
    style.configure("CardMuted.TLabel", background=p["card"],
                    foreground=p["muted"])

    if dark:
        style.configure("TFrame", background=p["bg"])
        style.configure("TLabel", background=p["bg"], foreground=p["text"])
        style.configure("TButton", background=p["button"],
                        foreground=p["text"], bordercolor=p["border"],
                        padding=(8, 4))
        style.map("TButton",
                  background=[("active", p["button_active"])],
                  foreground=[("disabled", p["muted"])])
        style.configure("TCheckbutton", background=p["bg"],
                        foreground=p["text"])
        style.map("TCheckbutton", background=[("active", p["bg"])])
        style.configure("TEntry", fieldbackground=p["entry"],
                        foreground=p["text"], insertcolor=p["text"])
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=p["bg"],
                        foreground=p["muted"], padding=(12, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", p["card"])],
                  foreground=[("selected", p["accent"])])
        style.configure("TProgressbar", background=p["accent"],
                        troughcolor=p["entry"], bordercolor=p["border"])
        style.configure("Accent.TButton", background=p["accent"],
                        foreground="#ffffff", bordercolor=p["accent"])
        style.map("Accent.TButton",
                  background=[("active", "#e06aa8")],
                  foreground=[("disabled", "#d9c2cf")])
        style.configure("Header.TFrame", background=p["header"])
        style.configure("Header.TLabel", background=p["header"],
                        foreground=p["text"])
    return p
