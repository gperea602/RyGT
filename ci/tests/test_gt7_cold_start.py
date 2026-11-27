# SPDX-License-Identifier: GPL-2.0-or-later
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnostics"))
from gt7_cold_start import HEADER, SERIAL, stage
sys.path.pop(0)


class ColdStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.output = self.source.parent / "new"
        self.manifest = self.source / (SERIAL + ".manifest")
        self.manifest.mkdir(parents=True)
        self.rec = self.manifest / f"{1:016x}-{3:016x}.rec"
        self.rec.write_bytes(HEADER.pack(b"RYGTMAN1", 4, 0, 0, 1, 2, 1, 3))

    def test_only_inputs_are_staged(self):
        capture = self.source / (SERIAL + ".capture")
        capture.mkdir()
        (capture / f"{1:016x}-{2:016x}.code").write_bytes(bytes(4))
        (self.manifest / "pipelines-10de-1234.rcp").write_bytes(b"RYGTRCP1")
        compute = self.source / (SERIAL + ".warm_compute")
        compute.mkdir()
        (compute / f"{1:#018x}-{2:#018x}.bin").write_bytes(struct.pack("<II", 0x43574752, 2))
        (self.source / "driver.cache").write_bytes(b"old")
        counts = stage(self.source, self.output)
        self.assertEqual(counts, dict(records=1, missing_code=0, graphics_catalogs=1, compute_recipes=1))
        self.assertTrue((self.output / self.manifest.name / "pipelines-seed-10de-1234.rcp").is_file())
        self.assertFalse((self.output / "driver.cache").exists())
        with self.assertRaises(ValueError):
            stage(self.source, self.output)

    def test_missing_code_cannot_publish_empty_seed(self):
        with self.assertRaisesRegex(ValueError, "1 records lack"):
            stage(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_bad_header_cannot_publish_partial_seed(self):
        self.rec.write_bytes(b"broken")
        with self.assertRaisesRegex(ValueError, "Truncated"):
            stage(self.source, self.output)
        self.assertFalse(self.output.exists())
