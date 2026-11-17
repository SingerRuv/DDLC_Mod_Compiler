"""Focused tests for the compiler backend and launcher library."""
import base64
import pickle
import shutil
import os
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ddlc_mod_manager import (builder, compiler_tab, config, devtools, guide_tab,
                              launcher_tab, library, mods, platforms,
                              rpa)  # noqa: E402
from ddlc_mod_manager import preflight as preflight_core  # noqa: E402
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
                 "open-folder", "output-folder", "sun", "moon", "help")
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

    def test_settings_keep_theme_and_last_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = config.SETTINGS_PATH
            try:
                config.SETTINGS_PATH = Path(tmp) / "settings.json"
                config.save_last_base("C:/DDLC")
                config.save_theme(True)
                self.assertTrue(config.load_theme())
                self.assertEqual(config.load_last_base(), "C:/DDLC")
                config.save_theme(False)
                self.assertFalse(config.load_theme())
                self.assertEqual(config.load_last_base(), "C:/DDLC")
                config.SETTINGS_PATH.write_text("[]", encoding="utf-8")
                self.assertFalse(config.load_theme())
                self.assertEqual(config.load_last_base(), "")
            finally:
                config.SETTINGS_PATH = old


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

    def test_base_info_editions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "renpy").mkdir()
            init = root / "renpy" / "__init__.py"
            init.write_text("version_tuple = (6, 99, 12, 4, 0)\n",
                            encoding="utf-8")
            self.assertEqual(mods.base_info(root),
                             ("6.99.12.4", "DDLC 1.1.1"))
            init.write_text("version_tuple = (6, 99, 12, 2, 0)\n",
                            encoding="utf-8")
            self.assertEqual(mods.base_info(root),
                             ("6.99.12.2", "DDLC 1.0.0"))

    def test_ddlc_build_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("DDLC.exe", "lib/x", "renpy/x",
                        "game/scripts.rpa", "game/mod_assets.rpa"):
                put(root, rel)
            self.assertEqual(mods.mod_kind(root), "DDLC build")


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

    def test_extract_archive_keeps_archive_and_skips_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "mod_assets.rpa"
            self._make_rpa(archive, "mod_assets/logo.png", self.PNG)
            dest = root / "game"
            result = rpa.extract_archive(archive, dest)
            self.assertEqual(result["files"], 1)
            self.assertEqual(
                (dest / "mod_assets/logo.png").read_bytes(), self.PNG)
            self.assertTrue(archive.is_file())
            result = rpa.extract_archive(archive, dest)
            self.assertEqual(result["files"], 0)
            self.assertEqual(result["skipped"], 1)
            result = rpa.extract_archive(archive, dest, overwrite=True)
            self.assertEqual(result["files"], 1)

    def test_extract_archive_blocks_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.rpa"
            self._make_rpa(archive, "../evil.png", self.PNG)
            with self.assertRaises(rpa.RPAError):
                rpa.extract_archive(archive, root / "game")

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
            self.assertFalse(out.with_name(out.name + ".tmp").exists())
            old_dir = library.DATA_DIR
            try:
                library.DATA_DIR = root / "data"
                logo = library._logo_for(root / "mod")
                self.assertTrue(Path(logo).is_file())
                self.assertEqual(Path(logo).read_bytes(), self.PNG)
            finally:
                library.DATA_DIR = old_dir

    def test_logo_extract_error_keeps_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mod"
            game = root / "game"
            game.mkdir(parents=True)
            self._make_rpa(game / "mod_assets.rpa", "mod_assets/logo.png",
                           self.PNG)
            put(root, "Game.exe")
            put(root, "Game.sh")
            old_dir = library.DATA_DIR
            try:
                library.DATA_DIR = Path(tmp) / "data"
                with mock.patch.object(library.rpa, "extract",
                                       side_effect=OSError("disk")):
                    entry = library.entry_from_path(root)
                self.assertIsNotNone(entry)
                self.assertEqual(entry["logo"], "")
            finally:
                library.DATA_DIR = old_dir

    def test_initial_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(library._logo_for(Path(tmp)), "")

    def test_malformed_rpa_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "broken.rpa"
            archive.write_bytes(b"not an RPA archive")
            self.assertEqual(rpa.list_images(archive), [])

    def test_index_cache_invalidates_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "mod_assets.rpa"
            self._make_rpa(archive, "mod_assets/logo1.png", self.PNG)
            first = rpa.list_images(archive)
            self._make_rpa(archive, "mod_assets/logo2.png", self.PNG)
            stamp = archive.stat().st_mtime_ns + 1_000_000
            os.utime(archive, ns=(stamp, stamp))
            second = rpa.list_images(archive)
            self.assertEqual(first[0][0], "mod_assets/logo1.png")
            self.assertEqual(second[0][0], "mod_assets/logo2.png")


class ZipSecurityTests(unittest.TestCase):
    def test_platform_name(self):
        self.assertIn(platform_name(), ("Windows", "macOS", "Linux"))

    def test_bad_launcher_names(self):
        self.assertTrue(platforms._bad_launcher("unins000.exe"))
        self.assertTrue(platforms._bad_launcher("Updater.exe"))
        self.assertFalse(platforms._bad_launcher("MyMod.exe"))

    def test_find_launcher_skips_uninstaller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if sys.platform == "win32":
                put(root, "unins000.exe")
                put(root, "MyMod.exe")
                expected = root / "MyMod.exe"
            elif sys.platform == "darwin":
                (root / "Uninstall.app").mkdir()
                (root / "MyMod.app").mkdir()
                expected = root / "MyMod.app"
            else:
                put(root, "uninstall.sh")
                put(root, "MyMod.sh")
                expected = root / "MyMod.sh"
            self.assertEqual(platforms.find_launcher(root), expected)

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

    def test_scan_ignores_build_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / (config.STAGING_PREFIX + "Mod-abc")
            staging.mkdir()
            put(staging, "Game.exe")
            good = root / "Good"
            good.mkdir()
            put(good, "Game.exe")
            entries = library.scan_mods(root)
            self.assertEqual([e["name"] for e in entries], ["Good"])

    def test_invalid_state_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_store = library.STORE_PATH
            try:
                library.STORE_PATH = Path(tmp) / "launcher.json"
                library.STORE_PATH.write_text("[]", encoding="utf-8")
                self.assertEqual(library.load_state(), ([], []))
                library.STORE_PATH.write_text('{"root": []}',
                                              encoding="utf-8")
                self.assertEqual(library.load_state(), ([], []))
            finally:
                library.STORE_PATH = old_store

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

    def test_rejects_output_containing_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            mod = root / "mod"
            base.mkdir()
            mod.mkdir()
            with self.assertRaises(BuildError):
                builder.validar_rutas(base, mod, root)
            with self.assertRaises(BuildError):
                builder.validar_rutas(base, mod, base / "out")


class PreflightTests(unittest.TestCase):
    def _base(self, root, version=(6, 99, 12, 4, 0), init=True):
        for rel in ("DDLC.exe", "lib/x", "renpy/x",
                    "game/python-packages/x.py", "game/scripts.rpa",
                    "game/images.rpa", "game/audio.rpa",
                    "game/fonts.rpa"):
            data = b"RPA-3.0 x" if rel.endswith(".rpa") else b"x"
            put(root, rel, data)
        if init:
            put(root, "renpy/__init__.py",
                ("version_tuple = (%s)\n" %
                 ", ".join(str(value) for value in version)).encode())

    def _overlay(self, root):
        put(root, "game/scripts.rpa", b"RPA-3.0 s")
        put(root, "game/mod_assets.rpa", b"RPA-3.0 m")

    def test_overlay_blocks_non_renpy6_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            mod = root / "mod"
            self._base(base, (7, 5, 3, 0))
            self._overlay(mod)
            with self.assertRaises(BuildError):
                preflight_core.preflight(base, mod, root / "out")

    def test_overlay_warns_unknown_base_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            mod = root / "mod"
            self._base(base, init=False)
            self._overlay(mod)
            report = preflight_core.preflight(base, mod, root / "out")
            self.assertEqual(report["mode"], "overlay")
            self.assertTrue(report["warnings"])

    def test_reports_replace_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            mod = root / "mod"
            self._base(base)
            self._overlay(mod)
            output = root / "out"
            put(output, "old.txt", b"old")
            output.with_name(output.name + ".zip").write_bytes(b"zip")
            report = preflight_core.preflight(
                base, mod, output, crear_zip=True, overwrite=True)
            self.assertTrue(report["replace"])
            self.assertTrue(report["zip_replace"])
            self.assertTrue(any("ZIP" in item for item in report["warnings"]))

    def test_format_report(self):
        report = {
            "mode": "overlay", "version": "",
            "base_edition": "DDLC 1.1.1", "base_version": "6.99.12.4",
            "output": "C:/out", "replace": True, "zip": "",
            "zip_replace": False, "free": 1024 ** 3,
            "warnings": ["warn"],
        }
        text = preflight_core.format_report(report)
        self.assertIn("Mode: DDLC overlay", text)
        self.assertIn("Warnings:", text)
        self.assertIn("Continue?", text)
        text = preflight_core.format_report(report, prompt=False)
        self.assertIn("Build diagnostics", text)
        self.assertNotIn("Continue?", text)

    def test_runtime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            mod = root / "mod"
            self._base(base)
            put(mod, "Game.exe", b"x")
            put(mod, "lib/py2-windows-x86_64/x", b"x")
            put(mod, "renpy/__init__.py",
                b"version_tuple = (7, 5, 3, 0)\n")
            put(mod, "game/scripts.rpa", b"RPA-3.0 s")
            put(mod, "game/mod_assets.rpa", b"RPA-3.0 m")
            report = preflight_core.preflight(base, mod, root / "out")
            self.assertEqual(report["mode"], "runtime")
            self.assertEqual(report["version"], "7")
            self.assertEqual(report["base_edition"], "DDLC 1.1.1")


class LauncherCacheTests(unittest.TestCase):
    def test_wheel_steps(self):
        self.assertEqual(launcher_tab._wheel_steps(120, "win32"), -1)
        self.assertEqual(launcher_tab._wheel_steps(-120, "win32"), 1)
        self.assertEqual(launcher_tab._wheel_steps(60, "win32"), -1)
        self.assertEqual(launcher_tab._wheel_steps(0, "win32"), 0)
        self.assertEqual(launcher_tab._wheel_steps(1, "darwin"), -1)
        self.assertEqual(launcher_tab._wheel_steps(-1, "darwin"), 1)

    def test_image_cache_key_changes_with_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo = Path(tmp) / "logo.png"
            logo.write_bytes(b"a")
            first = launcher_tab._image_cache_key(logo, 150)
            logo.write_bytes(b"bb")
            second = launcher_tab._image_cache_key(logo, 150)
            self.assertIsNotNone(first)
            self.assertNotEqual(first, second)
            self.assertIsNone(
                launcher_tab._image_cache_key(Path(tmp) / "missing.png"))


class LogTests(unittest.TestCase):
    def test_batch_writes_all_lines_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_path = compiler_tab.LOG_PATH
            try:
                compiler_tab.LOG_PATH = Path(tmp) / "build.log"
                compiler_tab._escribir_logs(["one", "two"])
                lines = compiler_tab.LOG_PATH.read_text(
                    encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(lines[0].endswith(" one"))
                self.assertTrue(lines[1].endswith(" two"))
            finally:
                compiler_tab.LOG_PATH = old_path


class GuideTests(unittest.TestCase):
    def test_empty_build_starts_at_base(self):
        done, current = guide_tab.build_step_states(
            "", "", "Mode: not detected", "")
        self.assertEqual(done, [False] * 5)
        self.assertEqual(current, 0)

    def test_build_states_follow_compiler_fields(self):
        done, current = guide_tab.build_step_states(
            "base", "mod", "Mode: DDLC overlay", "out")
        self.assertEqual(done[:4], [True] * 4)
        self.assertFalse(done[4])
        self.assertEqual(current, 4)

    def test_unrecognized_mod_stays_at_mod_step(self):
        done, current = guide_tab.build_step_states(
            "base", "mod", "Mode: not recognized", "out")
        self.assertFalse(done[1])
        self.assertEqual(current, 1)

    def test_building_and_built_states(self):
        done, current = guide_tab.build_step_states(
            "base", "mod", "Mode: Ren'Py runtime", "out", building=True)
        self.assertFalse(done[4])
        self.assertEqual(current, 4)
        done, current = guide_tab.build_step_states(
            "base", "mod", "Mode: Ren'Py runtime", "out", built=True)
        self.assertEqual(done, [True] * 5)
        self.assertEqual(current, 4)


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

    def test_snapshot_ignores_relative_parts_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "build" / "app"
            (root / "pkg").mkdir(parents=True)
            source = root / "pkg" / "app.py"
            source.write_text("x = 1\n", encoding="utf-8")
            dist = root / "dist" / "tool.py"
            dist.parent.mkdir()
            dist.write_text("x = 1\n", encoding="utf-8")
            snap = devtools.snapshot([root], root=root)
            self.assertIn(str(source), snap)
            self.assertNotIn(str(dist), snap)

    def test_build_staging_lists_pending_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / (config.STAGING_PREFIX + "Mod-abc")
            staging.mkdir()
            (root / "Real").mkdir()
            self.assertEqual(devtools.build_staging(root), [staging])

    def test_make_test_mods(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = devtools.make_test_mods(Path(tmp) / "dev", count=2)
            self.assertEqual(len(created), 2)
            self.assertTrue((created[0] / "Game.exe").is_file())
            self.assertTrue((created[0] / "Game.sh").is_file())
            self.assertTrue(
                (created[0] / "game" / "scripts.rpa").is_file())

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
