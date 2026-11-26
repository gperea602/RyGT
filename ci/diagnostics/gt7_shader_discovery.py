# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-901/902: diagnostic discovery route runner for shadGT's test bridge.

Requires a separately isolated offline test installation; the marker is an
operator assertion, not a sandbox. Does not launch the game or prove coverage.
"""
import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

SERIAL = "CUSA24769"
RECORD = re.compile(r"[0-9a-f]{16}-[0-9a-f]{16}\.rec", re.I)
ACTIONS = frozenset(("cross", "circle", "square", "triangle", "options",
                     "up", "down", "left", "right", "l1", "r1", "touchpad",
                     "shot", "shotwindow"))


def snapshot(cache, store):
    """Count observed identities, not successful Vulkan compilations."""
    def names(directory, predicate):
        return {p.name for p in directory.iterdir() if p.is_file() and predicate(p.name)} if directory.is_dir() else set()

    records = names(cache / (SERIAL + ".manifest"), lambda n: bool(RECORD.fullmatch(n)))
    return {
        "programs": {n.split("-")[0].lower() for n in records},
        "translations": {n.lower() for n in records},
        "graphics_keys": names(store, lambda n: n.startswith("g_") and n.endswith(".key")),
        "compute_recipes": names(cache / (SERIAL + ".warm_compute"), lambda n: n.endswith(".bin")),
    }


def delta(before, after):
    return {kind: {"before": len(values), "after": len(after[kind]),
                   "new": len(after[kind] - values), "removed": len(values - after[kind])}
            for kind, values in before.items()}


def validate_route(route):
    if not isinstance(route, list) or not route:
        raise ValueError("Route must be a non-empty array")
    seen = set()
    required = {"id", "action", "expect", "timeout_s"}
    for step in route:
        if not isinstance(step, dict) or not required <= set(step) <= required | {"observe_s"}:
            raise ValueError("Each step needs id, action, expect and timeout_s; observe_s is optional")
        ident, action, expect, timeout = (step[k] for k in ("id", "action", "expect", "timeout_s"))
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Step ids must be unique nonempty strings")
        seen.add(ident)
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("Unsupported action: " + repr(action))
        if not isinstance(expect, str) or not expect.strip():
            raise ValueError("A fresh game-state log event is required for each action")
        re.compile(expect)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 600:
            raise ValueError("timeout_s must be between 0 and 600")
        observe = step.get("observe_s", 2)
        if isinstance(observe, bool) or not isinstance(observe, (int, float)) or not 0 <= observe <= 600:
            raise ValueError("observe_s must be between 0 and 600")


def acknowledgment(action):
    if action == "shot":
        return "Ryty test script: screenshot at "
    if action == "shotwindow":
        return "Ryty test script: window screenshot at "
    return "Ryty test script: pressed " + action + " at "


class LogTail:
    def __init__(self, path):
        self.path = path
        stat = path.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.offset = stat.st_size
        self.pending = b""

    def read(self):
        with self.path.open("rb") as source:
            stat = os.fstat(source.fileno())
            if (stat.st_dev, stat.st_ino) != self.identity or stat.st_size < self.offset:
                raise RuntimeError("Log replaced or truncated during route; aborting")
            source.seek(self.offset)
            data = source.read()
            self.offset = source.tell()
        lines = (self.pending + data).split(b"\n")
        self.pending = lines.pop()
        return [line.decode("utf-8", errors="replace").rstrip("\r") for line in lines]

    def wait(self, pattern, timeout, stop, ack=None):
        deadline = time.monotonic() + timeout
        compiled = re.compile(pattern)
        acknowledged = ack is None
        observed = False
        while time.monotonic() < deadline:
            if stop.exists():
                raise RuntimeError("Stop requested")
            for line in self.read():
                if ack is not None and ack in line:
                    acknowledged = True
                elif compiled.search(line):
                    observed = True
            if acknowledged and observed:
                return
            time.sleep(0.05)
        raise TimeoutError(f"Missing fresh event or acknowledgment: {pattern}; ack={acknowledged}, event={observed}")


def observe(stop, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if stop.exists():
            raise RuntimeError("Stop requested")
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def checkpoint(report, result):
    """Publish a whole progress report after each confirmed step."""
    fd, tmp = tempfile.mkstemp(prefix=report.name + ".", dir=report.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, report)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_route(root, route, store, log, commands, report):
    validate_route(route)
    root = root.resolve()
    store, log, commands, report = (p.resolve() for p in (store, log, commands, report))
    if len({store, log, commands, report}) != 4 or any(root not in p.parents for p in (store, log, commands, report)):
        raise ValueError("Distinct route paths must be inside the sandbox")
    cache = root / "shaders"
    if not (root / ".gt7-preparation-sandbox").is_file():
        raise ValueError("Explicit isolated diagnostic sandbox marker required")
    if not cache.is_dir() or not store.is_dir() or store.parent != cache:
        raise ValueError("Select the active shader store directly inside sandbox/shaders")
    if not log.is_file() or not commands.is_file() or commands.stat().st_size != 0:
        raise ValueError("Live log and empty command file are required")
    stop = commands.with_suffix(commands.suffix + ".stop")
    tail = LogTail(log)
    initial = snapshot(cache, store)
    result = {"status": "running", "coverage": "observed identities only", "steps": [], "total_steps": len(route)}
    # Reserve a report without overwriting a previous run, then checkpoint atomically.
    with report.open("x", encoding="utf-8") as output:
        json.dump(result, output)
    try:
        for step in route:
            if stop.exists():
                raise RuntimeError("Stop requested")
            tail.read()
            tail.pending = b""
            before = snapshot(cache, store)
            with commands.open("a", encoding="ascii", newline="\n") as output:
                output.write(step["action"] + "\n")
                output.flush()
            tail.wait(step["expect"], step["timeout_s"], stop, acknowledgment(step["action"]))
            observe(stop, step.get("observe_s", 2))
            result["steps"].append({"id": step["id"], "observed": delta(before, snapshot(cache, store))})
            result["total_observed"] = delta(initial, snapshot(cache, store))
            checkpoint(report, result)
        result["status"] = "route_completed"
    except (OSError, RuntimeError, TimeoutError) as error:
        result["status"] = "incomplete"
        result["error"] = str(error)
    finally:
        result["total_observed"] = delta(initial, snapshot(cache, store))
        checkpoint(report, result)
    return result["status"] == "route_completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("sandbox", "store", "log", "commands", "route", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.sandbox.resolve()
    route = args.route.resolve()
    if root not in route.parents or route in {p.resolve() for p in (args.store, args.log, args.commands, args.report)}:
        parser.error("Route file must be distinct and inside the diagnostic sandbox")
    try:
        return 0 if run_route(root, json.loads(route.read_text(encoding="utf-8")),
                              args.store, args.log, args.commands, args.report) else 1
    except (OSError, ValueError, re.error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
