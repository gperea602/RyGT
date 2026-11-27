# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-905: conservative interpretation of observed GT7 1.71 log events."""
import re

RACE = re.compile(r'^\[patch\] GAME-00([26]) (\d\d:\d\d:\d\d\.\d{3}) GT7 (.+)$')
ATTEMPT = re.compile(r'Compiling (graphics|compute) pipeline (0x[0-9a-f]+)\b', re.I)
GRAPHICS = re.compile(r'Graphics pipeline ((?:[a-z]+_0x[0-9a-f]+)(?:,[a-z]+_0x[0-9a-f]+)*): (.+)', re.I)
COMPUTE = re.compile(r'compute pipeline (0x[0-9a-f]+) built by a worker .*?; (\d+) dispatches skipped meanwhile', re.I)


class RaceState:
    """No inference of track, menu, pause, or successful completion from an inactive flag."""
    def __init__(self):
        self.session = None
        self.running = None

    def observe(self, line):
        if line.startswith('[patch] GAME-002 GT7 race signal applied ('):
            # A newly installed observer has no evidence from this installation yet.
            self.session = None
            self.running = None
            return {'type': 'race_hook_installed'}
        match = RACE.fullmatch(line)
        if not match:
            return None
        code, clock, message = match.groups()
        if code == '2' and message.startswith('in a race:'):
            self.session = True
            self.running = None
        elif code == '2' and message.startswith('at the menus ('):
            # The hook may time out while loading: absence is not proof of menus.
            self.session = False
            self.running = None
        elif code == '6' and message == 'race starts (countdown or start)':
            self.running = True
        elif code == '6' and message == 'race not running (pre-race, finish, menus)':
            self.running = False
        else:
            return None
        return {'type': 'race_signal', 'code': 'GAME-00' + code, 'clock': clock,
                'session': self.session, 'running': self.running}


def pipeline_event(line):
    match = ATTEMPT.search(line)
    if match:
        kind, key = (v.lower() for v in match.groups())
        return {'type': 'attempt', 'kind': kind, 'key': key}
    match = COMPUTE.search(line)
    if match:
        return {'type': 'installed', 'kind': 'compute', 'key': match[1].lower(),
                'skipped_dispatches': int(match[2])}
    match = GRAPHICS.search(line)
    if match:
        # Stage hashes are not a full pipeline identity: fixed-function state can differ.
        return {'type': 'graphics_report', 'stages': match[1].lower(),
                'detail': match[2]}
    return None
