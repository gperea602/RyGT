# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-904: passive discovery timeline for an isolated diagnostics run.

Never sends input, launches the game, or classifies a scene from a guess.
Reports observed cache identities and logged compile attempts, not coverage.
"""
import argparse
import json
import math
import os
import re
import time
from pathlib import Path

from gt7_shader_discovery import LogTail, delta, snapshot

COMPILE = re.compile(r"Compiling (graphics|compute) pipeline (0x[0-9a-f]+)\b", re.I)


def survey(root, store, log, report, interval=2, duration=None):
    if not math.isfinite(interval) or not 0.05 <= interval <= 60:
        raise ValueError("interval must be between 0.05 and 60 seconds")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("duration must be positive and finite")
    root = root.resolve()
    store, log, report = (p.resolve() for p in (store, log, report))
    stop = report.with_suffix(report.suffix + ".stop").resolve()
    cache = root / "shaders"
    if len({store, log, report, stop}) != 4 or any(root not in p.parents for p in (store, log, report, stop)):
        raise ValueError("Distinct survey paths must be inside the sandbox")
    if cache in report.parents or cache in stop.parents:
        raise ValueError("Survey output must be outside the shader cache")
    if not (root / ".gt7-preparation-sandbox").is_file():
        raise ValueError("Explicit isolated diagnostic sandbox marker required")
    if not store.is_dir() or store.parent != cache or not log.is_file():
        raise ValueError("Select the active shader store and a live log")
    if stop.exists():
        raise ValueError("Remove stale stop file before starting a new survey")
    tail = LogTail(log)
    initial = snapshot(cache, store)
    previous = initial
    seen = {k: set(v) for k, v in initial.items()}
    attempts = {"graphics": set(), "compute": set()}
    start = time.monotonic()
    with report.open("x", encoding="utf-8", newline="\n") as output:
        def emit(event):
            output.write(json.dumps(event, ensure_ascii=True) + "\n")
            output.flush()
            os.fsync(output.fileno())

        emit({"type": "start", "schema": 1, "store": str(store.relative_to(root)),
              "log": str(log.relative_to(root)), "initial_log_offset": tail.offset,
              "initial_counts": {k: len(v) for k, v in initial.items()},
              "coverage": "observed identities only", "scene_state": "unclassified"})
        try:
            while True:
                # The original log remains the authoritative source. Preserve its
                # offsets for correlation with screenshots and manual observations.
                offset = tail.offset
                lines = tail.read()
                events = []
                for line in lines:
                    match = COMPILE.search(line)
                    if match:
                        kind, key = (v.lower() for v in match.groups())
                        attempts[kind].add(key)
                        events.append({"kind": kind, "key": key})
                current = snapshot(cache, store)
                for k in seen:
                    seen[k].update(current[k])
                elapsed = time.monotonic() - start
                emit({"type": "sample", "elapsed_s": round(elapsed, 3),
                      "log_start": offset, "log_end": tail.offset,
                      "log_lines": len(lines), "compile_events": events,
                      "unique_logged_compile_attempts": {k: len(v) for k, v in attempts.items()},
                      "observed": delta(previous, current),
                      "ever_new": {k: len(v - initial[k]) for k, v in seen.items()}})
                previous = current
                reason = "stop_requested" if stop.exists() else ("duration_reached" if duration is not None and elapsed >= duration else None)
                if reason:
                    emit({"type": "end", "reason": reason, "elapsed_s": round(elapsed, 3)})
                    return True
                time.sleep(interval if duration is None else min(interval, max(0, duration - elapsed)))
        except (OSError, RuntimeError) as error:
            emit({"type": "end", "reason": "incomplete", "error": str(error)})
            return False
        except KeyboardInterrupt:
            emit({"type": "end", "reason": "interrupted"})
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("sandbox", "store", "log", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--duration", type=float, help="Optional survey duration; otherwise stop file or Ctrl+C")
    args = parser.parse_args()
    try:
        return 0 if survey(args.sandbox, args.store, args.log, args.report,
                           args.interval, args.duration) else 1
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
