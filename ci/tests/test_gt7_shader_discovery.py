# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-901: synthetic route and cache tests; no game assets."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("gt7_discovery",
    Path(__file__).resolve().parents[1] / "diagnostics" / "gt7_shader_discovery.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class DiscoveryTests(unittest.TestCase):
    def test_new_identities_not_total_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            manifest = cache / "CUSA24769.manifest"
            store = cache / "CUSA24769"
            compute = cache / "CUSA24769.warm_compute"
            for folder in (manifest, store, compute):
                folder.mkdir()
            before = mod.snapshot(cache, store)
            for suffix in ("a", "b"):
                (manifest / ("1" * 16 + "-" + suffix * 16 + ".rec")).touch()
            (manifest / "invalid.rec").touch()
            (store / "g_sample.key").touch()
            (store / "unrelated.key").touch()
            (compute / "sample.bin").touch()
            observed = mod.delta(before, mod.snapshot(cache, store))
            self.assertEqual(observed["programs"]["new"], 1)
            self.assertEqual(observed["translations"]["new"], 2)
            self.assertEqual(observed["graphics_keys"]["new"], 1)
            self.assertEqual(observed["compute_recipes"]["new"], 1)

    def test_route_rejects_unbounded_or_unknown_steps(self):
        step = {"id": "menu", "action": "cross", "expect": "menu opened", "timeout_s": 5}
        mod.validate_route([step])
        for change in ({"timeout_s": 0}, {"timeout_s": 601}, {"expect": ""},
                       {"action": "r2on"}, {"action": "unknown"}, {"expect": "["}):
            with self.assertRaises((ValueError, mod.re.error)):
                mod.validate_route([dict(step, **change)])
        with self.assertRaises(ValueError):
            mod.validate_route([step, step])

    def test_log_ignores_stale_and_partial_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.log"
            path.write_bytes(b"stale event\n")
            tail = mod.LogTail(path)
            self.assertEqual(tail.read(), [])
            with path.open("ab") as f:
                f.write(b"fresh")
            self.assertEqual(tail.read(), [])
            with path.open("ab") as f:
                f.write(b" event\n")
            self.assertEqual(tail.read(), ["fresh event"])

    def test_stop_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log"
            log.touch()
            stop = Path(tmp) / "stop"
            stop.touch()
            with self.assertRaisesRegex(RuntimeError, "Stop requested"):
                mod.LogTail(log).wait("never", 1, stop)
