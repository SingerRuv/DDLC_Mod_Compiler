"""Focused tests for the compiler backend and launcher library."""
import base64
import pickle
import shutil
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ddlc_mod_manager import (builder, compiler_tab, config, devtools, library,
                              mods, rpa)  # noqa: E402
from ddlc_mod_manager.errors import BuildError  # noqa: E402
from ddlc_mod_manager.files import _extraer_zip  # noqa: E402
from ddlc_mod_manager.platforms import platform_name  # noqa: E402


def put(base, rel, data=b"x"):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class AssetsTests(unittest.TestCase):
    def test_icon_assets_exist(self):
        names = ("launcher", "compiler", "folder", "archive", "refresh",
                 "add-folder", "import", "build", "cancel", "play",
                 "open-folder", "output-folder", "sun", "moon")
        for variant in ("light", "dark"):
            for name in names:
                self.assertTrue((ROOT / "icons" / variant / (name + ".png"))
                                .is_file(), name)

    def test_compiler_tab_imports(self):
        self.assertTrue(callable(compiler_tab.compilar))

    def test_legacy_data_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old"
            new = Path(tmp) / "new"
            old.mkdir()
            (old / "launcher.json").write_text("{}", encoding="utf-8")
            (old / "settings.json").write_text('{"dark": true}',
                                               encoding="utf-8")
            self.assertTrue(config.migrate_legacy_data(old, new))
            self.assertTrue((new / "launcher.json").is_file())
            self.assertTrue((new / "settings.json").is_file())
            self.assertFalse(config.migrate_legacy_data(old, new))


class VersionTests(unittest.TestCase):
    def _runtime(self, root, major, lib_name):
        for rel in ("game/scripts.rpa", "Game.exe", "Game.sh"):
            put(root, rel)
        put(root, "renpy/__init__.py",
            ("version_tuple = (%d, 0, 0, 0)\n" % major).encode())
        (root / "lib" / lib_name).mkdir(parents=True)

    def test_runtime_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for major, lib_name in ((6, "pythonlib2.7"),
                                    (7, "py2-windows-x86_64"),
                                    (8, "py3-windows-x86_64")):
                mod = root / ("mod%d" % major)
                self._runtime(mod, major, lib_name)
                self.assertEqual(mods._version_renpy(mod), str(major))
                self.assertEqual(mods.mod_kind(mod), "Ren'Py %d" % major)

    def test_unknown_runtime_has_no_question_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / "mod"
            self._runtime(mod, 7, "unknown")
            (mod / "renpy" / "__init__.py").unlink()
            self.assertEqual(mods._version_renpy(mod), "")
            self.assertEqual(mods.mod_kind(mod), "Ren'Py runtime")

    def test_zip_version_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "mod.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("renpy/__init__.py",
                           "version_tuple = (8, 0, 3, 0)\n")
                z.writestr("lib/py3-windows-x86_64/x", "x")
                z.writestr("game/scripts.rpa", "RPA-3.0 x")
                z.writestr("Game.exe", "x")
            self.assertEqual(mods._tipo_zip(archive), ("runtime", "8"))


class RpaLogoTests(unittest.TestCase):
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII=")

    def _make_rpa(self, path, name, data):
        key = 0x42424242
        header_len = 34
        offset = 0
        for _ in range(4):
            index = pickle.dumps(
                {name: [(offset ^ key, len(data) ^ key)]}, protocol=3)
            compressed = zlib.compress(index)
            new_offset = header_len + len(compressed)
            if new_offset == offset:
                break
            offset = new_offset
        header = ("RPA-3.0 %016x %08x\n" % (header_len, key)).encode()
        path.write_bytes(header + compressed + data)

    def test_rpa_extract_and_library_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "mod" / "game"
            game.mkdir(parents=True)
            archive = game / "mod_assets.rpa"
            self._make_rpa(archive, "mod_assets/logo.png", self.PNG)
            images = rpa.list_images(archive)
            self.assertTrue(images)
            name, offset, length = images[0][0], images[0][1], images[0][2]
            self.assertEqual(name, "mod_assets/logo.png")
            out = root / "logo.png"
            self.assertIsNotNone(rpa.extract(archive, offset, length, out))
            old_dir = library.DATA_DIR
            try:
                library.DATA_DIR = root / "data"
                logo = library._logo_for(root / "mod")
                self.assertTrue(Path(logo).is_file())
                self.assertEqual(Path(logo).read_bytes(), self.PNG)
            finally:
                library.DATA_DIR = old_dir

    def test_initial_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(library._logo_for(Path(tmp)), "")


class ZipSecurityTests(unittest.TestCase):
    def test_platform_name(self):
        self.assertIn(platform_name(), ("Windows", "macOS", "Linux"))

    def test_filter_and_sort(self):
        entries = [
            {"name": "MySilver", "path": "/mods/MySilver",
             "kind": "Ren'Py 7", "mtime": 1},
            {"name": "Another", "path": "/mods/Another",
             "kind": "Ren'Py 8", "mtime": 3},
            {"name": "Vanilla", "path": "/mods/Vanilla",
             "kind": "DDLC build", "mtime": 2},
        ]
        by_name = library.filter_entries(entries, "silver")
        self.assertEqual([e["name"] for e in by_name], ["MySilver"])
        by_path = library.filter_entries(entries, "/mods/Another")
        self.assertEqual([e["name"] for e in by_path], ["Another"])
        only_7 = library.filter_entries(entries, "", "Ren'Py 7")
        self.assertEqual([e["name"] for e in only_7], ["MySilver"])
        other = library.filter_entries(entries, "", "Other")
        self.assertEqual(other, [])
        newest = library.sort_entries(entries, "Newest first")
        self.assertEqual([e["name"] for e in newest],
                         ["Another", "Vanilla", "MySilver"])

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


class DevReloadTests(unittest.TestCase):
    def test_snapshot_detects_changes_and_ignores_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            cache = root / "__pycache__" / "app.py"
            cache.parent.mkdir()
            cache.write_text("value = 1\n", encoding="utf-8")
            notes = root / "notes.txt"
            notes.write_text("ignored\n", encoding="utf-8")
            before = devtools.snapshot([root])
            self.assertIn(str(source), before)
            self.assertNotIn(str(cache), before)
            self.assertNotIn(str(notes), before)
            source.write_text("value = 12345\n", encoding="utf-8")
            self.assertNotEqual(before, devtools.snapshot([root]))

    def test_konami_code(self):
        code = devtools.Konami()
        keys = ("Up", "Down", "Up", "Down", "Left", "Right", "Left",
                "Right", "space", "space")
        results = [code.feed(key) for key in keys]
        self.assertEqual(results, [False] * 9 + [True])

    def test_konami_wrong_key_resets(self):
        code = devtools.Konami()
        for key in ("Up", "Down", "Up", "Down", "Escape"):
            self.assertFalse(code.feed(key))
        for key in ("Up", "Down", "Up", "Down", "Left", "Right", "Left",
                    "Right", "space", "space"):
            triggered = code.feed(key)
        self.assertTrue(triggered)


if __name__ == "__main__":
    unittest.main()
