# SPDX-License-Identifier: GPL-2.0-or-later
"""Synthetic passive-survey tests; no game or GPU is required."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnostics"))
import gt7_discovery_survey as mod
sys.path.pop(0)


class SurveyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.cache = self.root / "shaders"
        self.store = self.cache / "CUSA24769"
        self.store.mkdir(parents=True)
        self.manifest = self.cache / "CUSA24769.manifest"
        self.manifest.mkdir()
        self.log = self.root / "game.log"
        self.log.write_text("Compiling graphics pipeline 0xdead\n")
        self.report = self.root / "survey.jsonl"
        self.stop = self.root / "survey.jsonl.stop"
        (self.root / ".gt7-preparation-sandbox").touch()

    def run_survey(self, **kwargs):
        return mod.survey(self.root, self.store, self.log, self.report, 0.05, **kwargs)

    def records(self):
        return [json.loads(line) for line in self.report.read_text().splitlines()]

    def test_fresh_attempts_and_ever_seen_survive_removal(self):
        record = self.manifest / ("1" * 16 + "-" + "a" * 16 + ".rec")
        count = 0
        def advance(_):
            nonlocal count
            count += 1
            if count == 1:
                record.touch()
                with self.log.open("a") as out:
                    out.write("Compiling graphics pipeline 0x123\nCompiling graphics pipeline 0x123\nCompiling compute pipeline 0x456\n")
            else:
                record.unlink()
                self.stop.touch()
        with patch.object(mod.time, "sleep", side_effect=advance):
            self.assertTrue(self.run_survey())
        events = self.records()
        self.assertEqual(events[0]["scene_state"], "unclassified")
        self.assertEqual(events[-2]["ever_new"]["programs"], 1)
        self.assertEqual(events[-2]["observed"]["programs"]["removed"], 1)
        self.assertEqual(events[-2]["unique_logged_compile_attempts"], {"graphics": 1, "compute": 1})
        self.assertEqual(events[-1]["reason"], "stop_requested")
        self.assertNotIn("0xdead", self.report.read_text())

    def test_duration_and_existing_report(self):
        self.assertTrue(self.run_survey(duration=0.01))
        self.assertEqual(self.records()[-1]["reason"], "duration_reached")
        saved = self.report.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_survey(duration=0.01)
        self.assertEqual(self.report.read_bytes(), saved)

    def test_log_truncation_ends_incomplete(self):
        with patch.object(mod.time, "sleep", side_effect=lambda _: self.log.write_text("")):
            self.assertFalse(self.run_survey())
        self.assertEqual(self.records()[-1]["reason"], "incomplete")
        self.assertIn("truncated", self.records()[-1]["error"])

    def test_stale_stop_and_invalid_duration(self):
        for duration in (0, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                self.run_survey(duration=duration)
        self.stop.touch()
        with self.assertRaisesRegex(ValueError, "stale stop"):
            self.run_survey()
        self.assertFalse(self.report.exists())

    def test_marker_required(self):
        (self.root / ".gt7-preparation-sandbox").unlink()
        with self.assertRaises(ValueError):
            self.run_survey(duration=0.01)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
