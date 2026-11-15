"""Focused tests for the compiler backend and launcher library."""
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ddlc_mod_compiler import builder, library  # noqa: E402
from ddlc_mod_compiler.errors import BuildError  # noqa: E402
from ddlc_mod_compiler.files import _extraer_zip  # noqa: E402


def put(base, rel, data=b"x"):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class ZipSecurityTests(unittest.TestCase):
    def test_blocks_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../outside.txt", "bad")
            with self.assertRaises(BuildError):
                _extraer_zip(archive, Path(tmp) / "out")

    def test_blocks_drive_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("folder/C:/outside.txt", "bad")
            with self.assertRaises(BuildError):
                _extraer_zip(archive, Path(tmp) / "out")


class LibraryTests(unittest.TestCase):
    def test_scan_roots_only_runnable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "mods" / "Good"
            nested = good / "nested"
            nested.mkdir(parents=True)
            put(good, "Game.exe")
            put(good, "Game.sh")
            source = root / "mods" / "Source"
            put(source, "game/options.rpy")
            entries = library.scan_roots([root / "mods", root / "mods"])
            self.assertEqual([e["name"] for e in entries], ["Good"])

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_store = library.STORE_PATH
            old_dir = library.DATA_DIR
            try:
                library.DATA_DIR = Path(tmp)
                library.STORE_PATH = Path(tmp) / "launcher.json"
                mod = Path(tmp) / "My Mod"
                mod.mkdir()
                put(mod, "Game.exe")
                put(mod, "Game.sh")
                entry = library.entry_from_path(mod)
                library.save_state([str(mod.parent)], [entry])
                roots, paths = library.load_state()
                self.assertEqual(roots, [str(mod.parent)])
                self.assertEqual(paths, [entry["path"]])
            finally:
                library.STORE_PATH = old_store
                library.DATA_DIR = old_dir


class BuilderTests(unittest.TestCase):
    def test_overwrite_replaces_output_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            for rel, data in [
                ("DDLC.exe", b"e"), ("DDLC.sh", b"e"),
                ("lib/x", b"x"), ("renpy/x", b"x"),
                ("game/scripts.rpa", b"RPA-3.0 s"),
                ("game/images.rpa", b"RPA-3.0 i"),
                ("game/audio.rpa", b"RPA-3.0 a"),
                ("game/fonts.rpa", b"RPA-3.0 f"),
                ("game/python-packages/x.py", b"x"),
            ]:
                put(base, rel, data)
            mod = root / "mod"
            for rel, data in [
                ("Game.exe", b"e"), ("Game.sh", b"e"),
                ("lib/py2-windows-x86_64/x", b"x"), ("renpy/x", b"x"),
                ("game/scripts.rpa", b"RPA-3.0 m"),
                ("game/mod_assets.rpa", b"RPA-3.0 ma"),
            ]:
                put(mod, rel, data)
            output = root / "DDLC My Mod"
            builder.compilar(base, mod, output, log=lambda *_: None,
                             status=lambda *_: None,
                             progress=lambda *_: None)
            put(output, "stale.txt", b"old")
            builder.compilar(base, mod, output, crear_zip=True,
                             overwrite=True, log=lambda *_: None,
                             status=lambda *_: None,
                             progress=lambda *_: None)
            self.assertFalse((output / "stale.txt").exists())
            self.assertTrue((output / "Game.exe").is_file())
            self.assertTrue(output.with_name(output.name + ".zip").is_file())
            self.assertFalse(
                output.with_name(output.name + ".ddlc-backup").exists())


if __name__ == "__main__":
    unittest.main()
