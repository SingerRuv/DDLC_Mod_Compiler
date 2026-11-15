"""Minimal, safe reader for Ren'Py RPA-3.0 archives."""
import io
import pickle
import zlib
from collections import OrderedDict
from pathlib import Path

MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_LOGO_BYTES = 32 * 1024 * 1024
INDEX_CHUNK = 64 * 1024
INDEX_CACHE_LIMIT = 64
INDEX_CACHE_BYTES = 16 * 1024 * 1024
IMAGE_SUFFIXES = (".png", ".gif")
_INDEX_CACHE = OrderedDict()
_INDEX_CACHE_BYTES = 0


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("RPA index classes are not allowed")


def _parse_index(path):
    try:
        with open(path, "rb") as fh:
            header = fh.readline(80).decode("ascii", "ignore").strip()
            parts = header.split()
            if len(parts) < 3 or parts[0] != "RPA-3.0":
                return {}, 0, 0
            try:
                offset = int(parts[1], 16)
                key = int(parts[2], 16)
            except ValueError:
                return {}, 0, 0
            fh.seek(offset)
            decompressor = zlib.decompressobj()
            chunks = []
            total = 0
            while True:
                block = fh.read(INDEX_CHUNK)
                if not block:
                    break
                while block:
                    remaining = MAX_INDEX_BYTES - total
                    if remaining <= 0:
                        return {}, 0, 0
                    data = decompressor.decompress(block, remaining)
                    if data:
                        chunks.append(data)
                        total += len(data)
                    block = decompressor.unconsumed_tail
                    if decompressor.eof:
                        break
                if decompressor.eof:
                    break
            if not decompressor.eof:
                return {}, 0, 0
            index = _SafeUnpickler(
                io.BytesIO(b"".join(chunks)), encoding="bytes").load()
            return index, key, total
    except Exception:
        return {}, 0, 0


def _read_index(path):
    global _INDEX_CACHE_BYTES
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return {}, 0
    cache_key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _INDEX_CACHE.get(cache_key)
    if cached is not None:
        _INDEX_CACHE.move_to_end(cache_key)
        return cached[0], cached[1]
    result = _parse_index(path)
    _INDEX_CACHE[cache_key] = result
    _INDEX_CACHE_BYTES += result[2]
    _trim_index_cache()
    return result[0], result[1]


def _trim_index_cache():
    global _INDEX_CACHE_BYTES
    while _INDEX_CACHE and (len(_INDEX_CACHE) > INDEX_CACHE_LIMIT or
                            _INDEX_CACHE_BYTES > INDEX_CACHE_BYTES):
        _key, value = _INDEX_CACHE.popitem(last=False)
        _INDEX_CACHE_BYTES -= value[2]


def list_images(path):
    """Return (name, offset, length) for PNG/GIF entries in an RPA."""
    index, key = _read_index(path)
    if not isinstance(index, dict):
        return []
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
