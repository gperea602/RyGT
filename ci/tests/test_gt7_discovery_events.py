# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diagnostics'))
from gt7_discovery_events import RaceState, pipeline_event
sys.path.pop(0)


class DiscoveryEventTests(unittest.TestCase):
    def test_race_signals_do_not_infer_menu_or_pause(self):
        state = RaceState()
        self.assertEqual(state.observe('[patch] GAME-002 GT7 race signal applied (org_race\'s gate)')['type'], 'race_hook_installed')
        self.assertIsNone(state.running)
        event = state.observe('[patch] GAME-002 09:59:37.501 GT7 in a race: the race code runs (org_race\'s gate is open)')
        self.assertTrue(event['session'])
        self.assertIsNone(event['running'])
        self.assertTrue(state.observe('[patch] GAME-006 09:59:52.544 GT7 race starts (countdown or start)')['running'])
        event = state.observe('[patch] GAME-006 10:01:04.978 GT7 race not running (pre-race, finish, menus)')
        self.assertTrue(event['session'])
        self.assertFalse(event['running'])
        event = state.observe('[patch] GAME-002 10:01:05.000 GT7 at the menus (org_race has not run for five seconds)')
        self.assertFalse(event['session'])
        self.assertIsNone(event['running'])

    def test_reinstalled_hook_invalidates_previous_race(self):
        state = RaceState()
        state.observe("[patch] GAME-002 09:59:37.501 GT7 in a race: the race code runs (org_race's gate is open)")
        state.observe('[patch] GAME-006 09:59:52.544 GT7 race starts (countdown or start)')
        self.assertTrue(state.session)
        self.assertTrue(state.running)
        state.observe("[patch] GAME-002 GT7 race signal applied (org_race's gate)")
        self.assertIsNone(state.session)
        self.assertIsNone(state.running)
        event = state.observe('[patch] GAME-006 10:00:00.000 GT7 race starts (countdown or start)')
        self.assertIsNone(event['session'])
        self.assertTrue(event['running'])

    def test_unrecognized_and_other_game_ignored(self):
        state = RaceState()
        self.assertIsNone(state.observe('[patch] GAME-006 10:01:04.978 GTS race starts (countdown or start)'))
        self.assertIsNone(state.observe('[patch] GAME-006 10:01:04.978 GT7 invented state'))
        self.assertIsNone(state.running)

    def test_pipeline_events_keep_separate_semantics(self):
        self.assertEqual(pipeline_event('Compiling graphics pipeline 0x123')['type'], 'attempt')
        event = pipeline_event('compute pipeline 0xc08bf56ce6023582 built by a worker 0 ms after it was queued, installed 0 ms after; 3 dispatches skipped meanwhile')
        self.assertEqual(event['type'], 'installed')
        self.assertEqual(event['skipped_dispatches'], 3)
        event = pipeline_event('Graphics pipeline fs_0x000000009c23f9ea,vs_0x000000008167a22c: libraries 0.7 ms (pre-raster compiled, fragment compiled), fast link 0.0 ms')
        self.assertEqual(event['type'], 'graphics_report')
        self.assertNotIn('key', event)
        self.assertIsNone(pipeline_event('unrelated line'))


if __name__ == '__main__':
    unittest.main()
