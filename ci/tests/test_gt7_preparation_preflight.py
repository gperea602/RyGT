# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

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
        self.assertTrue(any("hardlinked" in item for item in self.check()))

    def test_symlink(self):
        try:
            (self.sandbox / "user" / "linked").symlink_to(self.player, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        self.assertTrue(any("Link/reparse" in item for item in self.check()))


if __name__ == "__main__":
    unittest.main()
