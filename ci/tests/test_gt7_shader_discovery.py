# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-902: test the discovery protocol with a synthetic bridge, not GT7."""
import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("gt7_discovery",
    Path(__file__).resolve().parents[1] / "diagnostics" / "gt7_shader_discovery.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def step(ident="menu", action="cross", expect="menu opened", timeout=1):
    return {"id": ident, "action": action, "expect": expect, "timeout_s": timeout, "observe_s": 0}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / "shaders"
        self.store = self.cache / "CUSA24769"
        self.manifest = self.cache / "CUSA24769.manifest"
        self.compute = self.cache / "CUSA24769.warm_compute"
        for folder in (self.store, self.manifest, self.compute):
            folder.mkdir(parents=True)
        (self.root / ".gt7-preparation-sandbox").touch()
        self.log, self.commands, self.report = (self.root / name for name in ("log", "commands", "report.json"))
        self.log.touch()
        self.commands.touch()
        self.stop = self.commands.with_suffix(".stop")

    def run_route(self, route):
        return mod.run_route(self.root, route, self.store, self.log, self.commands, self.report)

    def append_log(self, text):
        with self.log.open("a", encoding="utf-8") as output:
            output.write(text + "\n")

    def bridge(self, callback):
        finished = threading.Event()
        def work():
            sent = 0
            while not finished.is_set():
                lines = self.commands.read_text().splitlines()
                for action in lines[sent:]:
                    callback(action)
                    sent += 1
                finished.wait(0.005)
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        def cleanup():
            finished.set()
            thread.join(2)
        self.addCleanup(cleanup)

    def test_new_identities_not_total_coverage(self):
        before = mod.snapshot(self.cache, self.store)
        for suffix in ("a", "b"):
            (self.manifest / ("1" * 16 + "-" + suffix * 16 + ".rec")).touch()
        (self.manifest / "invalid.rec").touch()
        (self.store / "g_sample.key").touch()
        (self.store / "unrelated.key").touch()
        (self.compute / "sample.bin").touch()
        observed = mod.delta(before, mod.snapshot(self.cache, self.store))
        self.assertEqual([observed[k]["new"] for k in observed], [1, 2, 1, 1])

    def test_route_rejects_invalid_steps(self):
        for change in ({"timeout_s": 0}, {"timeout_s": 601}, {"expect": ""},
                       {"action": "r2on"}, {"action": "unknown"}, {"expect": "["}, {"observe_s": -1}):
            with self.assertRaises((ValueError, mod.re.error)):
                mod.validate_route([dict(step(), **change)])
        with self.assertRaises(ValueError):
            mod.validate_route([step(), step()])

    def test_log_ignores_stale_and_partial_events(self):
        self.append_log("stale event")
        tail = mod.LogTail(self.log)
        self.assertEqual(tail.read(), [])
        with self.log.open("ab") as f:
            f.write(b"fresh")
        self.assertEqual(tail.read(), [])
        with self.log.open("ab") as f:
            f.write(b" event\n")
        self.assertEqual(tail.read(), ["fresh event"])

    def test_stop_is_respected(self):
        self.stop.touch()
        with self.assertRaisesRegex(RuntimeError, "Stop requested"):
            mod.LogTail(self.log).wait("never", 1, self.stop)

    def test_complete_route_discovers_new_resources(self):
        def simulate(action):
            if action == "cross":
                (self.manifest / ("1" * 16 + "-" + "a" * 16 + ".rec")).touch()
                self.append_log("menu opened")  # state may arrive before the release acknowledgment
            else:
                (self.store / "g_track.key").touch()
                (self.compute / "track.bin").touch()
                self.append_log("track loaded")
            self.append_log(mod.acknowledgment(action) + "0.1 s")
        self.bridge(simulate)
        self.assertTrue(self.run_route([step(), step("track", "right", "track loaded")]))
        report = json.loads(self.report.read_text())
        self.assertEqual(report["status"], "route_completed")
        self.assertEqual(len(report["steps"]), 2)
        self.assertEqual(report["total_observed"]["graphics_keys"]["new"], 1)
        self.assertEqual(report["total_observed"]["compute_recipes"]["new"], 1)
        self.assertEqual(report["total_observed"]["programs"]["new"], 1)

    def test_missing_ack_preserves_partial_checkpoint(self):
        def simulate(action):
            if action == "cross":
                self.append_log("menu opened")
                self.append_log(mod.acknowledgment(action) + "0.1 s")
            else:
                self.append_log("track loaded")  # no acknowledgment
        self.bridge(simulate)
        self.assertFalse(self.run_route([step(), step("track", "right", "track loaded", 0.25)]))
        report = json.loads(self.report.read_text())
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(len(report["steps"]), 1)
        self.assertIn("ack=False", report["error"])

    def test_ack_without_game_event_fails(self):
        self.bridge(lambda action: self.append_log(mod.acknowledgment(action) + "0.1 s"))
        self.assertFalse(self.run_route([step(timeout=0.25)]))
        report = json.loads(self.report.read_text())
        self.assertEqual(report["steps"], [])
        self.assertIn("event=False", report["error"])

    def test_existing_report_is_not_overwritten(self):
        self.report.write_text("previous result")
        with self.assertRaises(FileExistsError):
            self.run_route([step()])
        self.assertEqual(self.report.read_text(), "previous result")

    def test_no_marker_no_commands(self):
        (self.root / ".gt7-preparation-sandbox").unlink()
        with self.assertRaises(ValueError):
            self.run_route([step()])
        self.assertEqual(self.commands.read_text(), "")


if __name__ == "__main__":
    unittest.main()
