"""Small PNG icon loader with a cache."""
import tkinter as tk

from .config import resource_path

_CACHE = {}


def get_icon(name, dark=False):
    key = (name, bool(dark))
    if key in _CACHE:
        return _CACHE[key]
    variant = "dark" if dark else "light"
    path = resource_path("icons/%s/%s.png" % (variant, name))
    try:
        image = tk.PhotoImage(file=str(path))
    except Exception:
        image = None
    _CACHE[key] = image
    return image
