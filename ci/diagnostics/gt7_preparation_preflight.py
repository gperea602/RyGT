# SPDX-License-Identifier: GPL-2.0-or-later
"""Preflight check for an independently copied GT7 diagnostic installation.

Not an OS sandbox or network firewall. Does not start GT7, change configuration,
or create a ready marker. Run under the same environment as the planned session.
"""
import argparse
import json
import os
import stat
from pathlib import Path

SERIAL = "CUSA24769"


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def linked(st):
    return (stat.S_ISLNK(st.st_mode) or
            bool(getattr(st, "st_file_attributes", 0) &
                 getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def audit(sandbox, player, env):
    issues = []
    sandbox, player = Path(sandbox), Path(player)
    for label, path in (("sandbox", sandbox), ("player", player)):
        if not path.is_dir():
            issues.append(label + " root must be an existing directory")
        for part in (path.absolute(), *path.absolute().parents):
            if linked(part.lstat()):
                issues.append(label + " path contains a link or reparse point: " + str(part))
    root, original = sandbox.resolve(), player.resolve()
    if overlaps(root, original):
        issues.append("Sandbox and player roots overlap")
    if issues:
        return issues

    for required in ("GT7.exe", "user", "libs", "shaders"):
        if not (root / required).exists():
            issues.append("Missing required path: " + required)

    # Reject links, junctions and hardlinked files throughout the copied tree.
    # A hardlink permits writes through either name, even across separate roots.
    def scan(directory):
        with os.scandir(directory) as entries:
            for entry in entries:
                st = entry.stat(follow_symlinks=False)
                if linked(st):
                    issues.append("Link/reparse point: " + str(entry.path))
                elif stat.S_ISDIR(st.st_mode):
                    scan(entry.path)
                elif not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    issues.append("Special or hardlinked file: " + str(entry.path))

    scan(root)
    if issues:
        return issues

    # Match the runtime's AppOverlay.cpp: env takes precedence over game/update
    # in the per-title INI. For first diagnostics insist on local copies.
    layers = env.get("RYGT_APP0_LAYERS", "")
    values = layers.split(";") if layers else []
    ini = root / (SERIAL + ".RyGT.ini")
    legacy = root / "RyGT.ini"
    for settings in (ini, legacy):
        if settings.is_file():
            for line in settings.read_text(encoding="utf-8-sig").splitlines():
                key, sep, value = line.partition("=")
                if sep and key.strip() in {"game", "update"} and value.strip():
                    values.append(value.strip())
    for value in values:
        if not value:
            continue
        path = Path(value)
        path = (path if path.is_absolute() else root / path).resolve()
        if root not in path.parents or not path.is_dir():
            issues.append("App0 layer must be an existing directory inside sandbox: " + value)

    # Reject explicit log paths that could escape the copy.
    if env.get("RYGT_LOG_DIRECTORY"):
        p = Path(env["RYGT_LOG_DIRECTORY"])
        p = (p if p.is_absolute() else root / p).resolve()
        if root not in p.parents:
            issues.append("RYGT_LOG_DIRECTORY points outside sandbox")

    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", type=Path, required=True)
    parser.add_argument("--player-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        issues = audit(args.sandbox, args.player_root, os.environ)
    except (OSError, ValueError) as error:
        issues = [str(error)]
    print(json.dumps({"filesystem_preflight": "failed" if issues else "passed",
                      "issues": issues, "network_isolation_verified": False,
                      "runtime_isolation_verified": False}, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
