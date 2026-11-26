# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("preflight",
    Path(__file__).resolve().parents[1] / "diagnostics" / "gt7_preparation_preflight.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.player, self.sandbox = root / "player", root / "sandbox"
        self.player.mkdir()
        self.sandbox.mkdir()
        (self.sandbox / "GT7.exe").touch()
        for name in ("user", "libs", "shaders", "app0"):
            (self.sandbox / name).mkdir()

    def check(self, env=None):
        return mod.audit(self.sandbox, self.player, env or {})

    def test_independent_copy(self):
        self.assertEqual(self.check(), [])

    def test_unknown_link_count_is_rejected(self):
        # Fail closed if even the direct stat cannot obtain the link count.
        original_stat = os.stat
        target = self.sandbox / "GT7.exe"

        def missing_link_count(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if Path(path) == target:
                values = list(result)
                values[3] = 0  # st_nlink
                return os.stat_result(values)
            return result

        with patch.object(mod.os, "stat", side_effect=missing_link_count):
            issues = self.check()
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("GT7.exe", issues[0])

    def test_overlap(self):
        self.assertTrue(mod.audit(self.player, self.player, {}))

    def test_external_layer(self):
        self.assertTrue(self.check({"RYGT_APP0_LAYERS": str(self.player)}))

    def test_local_layer(self):
        self.assertEqual(self.check({"RYGT_APP0_LAYERS": "app0"}), [])

    def test_external_ini(self):
        (self.sandbox / "CUSA24769.RyGT.ini").write_text("game=" + str(self.player))
        self.assertTrue(self.check())

    def test_external_logs(self):
        self.assertTrue(self.check({"RYGT_LOG_DIRECTORY": str(self.player)}))

    def test_hardlink(self):
        target = self.player / "save.bin"
        target.touch()
        try:
            os.link(target, self.sandbox / "user" / "save.bin")
        except OSError as error:
            self.skipTest(str(error))
        issues = self.check()
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("hardlinked", issues[0])
        self.assertIn("save.bin", issues[0])

    def test_symlink(self):
        try:
            (self.sandbox / "user" / "linked").symlink_to(self.player, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        self.assertTrue(any("Link/reparse" in item for item in self.check()))


if __name__ == "__main__":
    unittest.main()
