# SPDX-License-Identifier: GPL-2.0-or-later
"""FEAT-GT7-906: stage private shadGT recipe inputs for an empty GT7 shader store."""
import argparse
import json
import re
import shutil
import struct
import tempfile
from pathlib import Path

SERIAL = "CUSA24769"
HEADER = struct.Struct("<8sIIIQQIQ")
RECORD = re.compile(r"[0-9a-f]{16}-[0-9a-f]{16}\.rec")
GRAPHICS = re.compile(r"pipelines-[0-9a-f]{4}-[0-9a-f]{4}\.rcp")
COMPUTE = re.compile(r"0x[0-9a-f]{16}-0x[0-9a-f]{16}\.bin")


def stage(source, destination):
    source, destination = source.resolve(strict=True), destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Output must be a new directory. Existing caches are never replaced.")
    if source == destination.parent.resolve() or source in destination.parent.resolve().parents:
        raise ValueError("Output must be outside the source tree.")
    manifest = source / (SERIAL + ".manifest")
    capture = source / (SERIAL + ".capture")
    compute = source / (SERIAL + ".warm_compute")
    counts = dict(records=0, missing_code=0, graphics_catalogs=0, compute_recipes=0)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        root = Path(temp) / "shaders"
        root.mkdir()

        def copy(file, name=None):
            folder = root / file.parent.name
            folder.mkdir(exist_ok=True)
            target = folder / (name or file.name)
            if not target.exists():
                shutil.copyfile(file, target)

        for file in manifest.glob("*.rec"):
            if not RECORD.fullmatch(file.name):
                continue
            with file.open("rb") as stream:
                header = stream.read(HEADER.size)
            if len(header) != HEADER.size:
                raise ValueError(f"Truncated record: {file.name}")
            magic, version, _, _, program, digest, words, variant = HEADER.unpack(header)
            if (magic != b"RYGTMAN1" or not 1 <= version <= 4 or not words
                    or file.name != f"{program:016x}-{variant:016x}.rec"):
                raise ValueError(f"Incompatible record: {file.name}")
            code = capture / f"{program:016x}-{digest:016x}.code"
            if not code.is_file() or code.stat().st_size != words * 4:
                counts["missing_code"] += 1
                continue
            copy(code)
            copy(file)
            counts["records"] += 1
        if counts["records"]:
            for file in manifest.glob("pipelines-*.rcp"):
                if GRAPHICS.fullmatch(file.name):
                    with file.open("rb") as stream:
                        if stream.read(8) != b"RYGTRCP1":
                            raise ValueError(f"Incompatible catalog: {file.name}")
                    # ImportForeignPipelines reserves the local GPU's canonical name for export.
                    copy(file, file.name.replace("pipelines-", "pipelines-seed-", 1))
                    counts["graphics_catalogs"] += 1
        for file in compute.glob("*.bin"):
            if COMPUTE.fullmatch(file.name):
                with file.open("rb") as stream:
                    if stream.read(8) != struct.pack("<II", 0x43574752, 2):
                        raise ValueError(f"Incompatible compute recipe: {file.name}")
                copy(file)
                counts["compute_recipes"] += 1
        if not counts["records"] and not counts["compute_recipes"]:
            raise ValueError(f"No replay inputs found ({counts['missing_code']} records lack captured code).")
        root.rename(destination)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.source, args.output)))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
