# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-901: diagnostic route runner for the existing shadGT test input bridge.

This does not launch GT7, claim complete coverage, or manipulate protected assets.
Run only with a separately isolated offline test installation and a diagnostics
renderer with RYTY_TEST_SCRIPT_FILE pointing to the command file.
"""
import argparse
import json
import re
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
    for step in route:
        if not isinstance(step, dict) or set(step) != {"id", "action", "expect", "timeout_s"}:
            raise ValueError("Each step needs id, action, expect and timeout_s")
        ident, action, expect, timeout = (step[k] for k in ("id", "action", "expect", "timeout_s"))
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Step ids must be unique nonempty strings")
        seen.add(ident)
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("Unsupported action: " + repr(action))
        if not isinstance(expect, str) or not expect.strip():
            raise ValueError("A fresh log event is required for each action")
        re.compile(expect)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 600:
            raise ValueError("timeout_s must be between 0 and 600")


class LogTail:
    def __init__(self, path):
        self.path = path
        self.offset = path.stat().st_size
        self.pending = b""

    def read(self):
        with self.path.open("rb") as source:
            if source.seek(0, 2) < self.offset:
                raise RuntimeError("Log truncated during route; aborting")
            source.seek(self.offset)
            data = source.read()
            self.offset = source.tell()
        lines = (self.pending + data).split(b"\n")
        self.pending = lines.pop()
        return [line.decode("utf-8", errors="replace").rstrip("\r") for line in lines]

    def wait(self, pattern, timeout, stop):
        deadline = time.monotonic() + timeout
        compiled = re.compile(pattern)
        while time.monotonic() < deadline:
            if stop.exists():
                raise RuntimeError("Stop requested")
            if any(compiled.search(line) for line in self.read()):
                return
            time.sleep(0.1)
        raise TimeoutError("Expected fresh event not observed: " + pattern)


def run_route(root, route, store, log, commands, report):
    validate_route(route)
    cache = root / "shaders"
    if not (root / ".gt7-preparation-sandbox").is_file():
        raise ValueError("Explicit isolated diagnostic sandbox marker required")
    if not cache.is_dir() or not store.is_dir() or store.parent != cache:
        raise ValueError("Select the active shader store directly inside sandbox/shaders")
    if not log.is_file() or not commands.is_file() or commands.stat().st_size != 0:
        raise ValueError("Live log and empty command file are required")
    if report.exists():
        raise ValueError("Report already exists; choose a new path")
    stop = commands.with_suffix(commands.suffix + ".stop")
    tail = LogTail(log)
    result = {"status": "running", "coverage": "observed identities only", "steps": []}
    try:
        for step in route:
            if stop.exists():
                raise RuntimeError("Stop requested")
            # Discard previous events before the new action; do not accept stale acknowledgements.
            tail.read()
            tail.pending = b""
            before = snapshot(cache, store)
            with commands.open("a", encoding="ascii", newline="\n") as output:
                output.write(step["action"] + "\n")
                output.flush()
            tail.wait(step["expect"], step["timeout_s"], stop)
            result["steps"].append({"id": step["id"], "observed": delta(before, snapshot(cache, store))})
        result["status"] = "route_completed"
    except (OSError, RuntimeError, TimeoutError) as error:
        result["status"] = "incomplete"
        result["error"] = str(error)
    finally:
        with report.open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
    return result["status"] == "route_completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--commands", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.sandbox.resolve()
    paths = [p.resolve() for p in (args.store, args.log, args.commands, args.route, args.report)]
    if any(root not in p.parents for p in paths):
        parser.error("All paths must be inside the diagnostic sandbox")
    store, log, commands, route, report = paths
    try:
        return 0 if run_route(root, json.loads(route.read_text(encoding="utf-8")),
                              store, log, commands, report) else 1
    except (OSError, ValueError, re.error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
