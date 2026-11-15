"""Minimal, safe reader for Ren'Py RPA-3.0 archives."""
import io
import pickle
import zlib
from pathlib import Path

MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_LOGO_BYTES = 32 * 1024 * 1024
IMAGE_SUFFIXES = (".png", ".gif")


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("RPA index classes are not allowed")


def _index(path):
    with open(path, "rb") as fh:
        header = fh.readline(80).decode("ascii", "ignore").strip()
        parts = header.split()
        if len(parts) < 3 or parts[0] != "RPA-3.0":
            return {}
        try:
            offset = int(parts[1], 16)
            key = int(parts[2], 16)
        except ValueError:
            return {}
        fh.seek(offset)
        try:
            raw = zlib.decompressobj().decompress(
                fh.read(), MAX_INDEX_BYTES)
            return _SafeUnpickler(
                io.BytesIO(raw), encoding="bytes").load()
        except Exception:
            return {}


def list_images(path):
    """Return (name, offset, length) for PNG/GIF entries in an RPA."""
    index = _index(path)
    if not isinstance(index, dict):
        return []
    key = _key(path)
    result = []
    for name, values in index.items():
        if isinstance(name, bytes):
            name = name.decode("utf-8", "ignore")
        if not isinstance(name, str) or not name.lower().endswith(
                IMAGE_SUFFIXES):
            continue
        if not values:
            continue
        entry = values[0]
        try:
            if len(entry) == 2:
                offset, length = entry
                prefix = key
            else:
                offset, length, prefix = entry[:3]
                if prefix:
                    prefix = int.from_bytes(prefix, "big") if isinstance(
                        prefix, bytes) else int(prefix)
                else:
                    prefix = key
            result.append((name, int(offset) ^ int(prefix),
                           int(length) ^ int(prefix)))
        except (TypeError, ValueError, OSError):
            continue
    return result


def _key(path):
    with open(path, "rb") as fh:
        parts = fh.readline(80).decode("ascii", "ignore").split()
    return int(parts[2], 16)


def extract(path, offset, length, destination):
    if length <= 0 or length > MAX_LOGO_BYTES:
        return None
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(length)
    if len(data) != length:
        return None
    destination.write_bytes(data)
    return destination
