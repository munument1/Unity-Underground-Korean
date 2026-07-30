#!/usr/bin/env python3
"""Extract Ultima Underworld 1 data/strings.pak from GOG's game.gog ISO."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SECTOR_SIZE = 2048


class IsoFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IsoEntry:
    extent: int
    size: int
    is_directory: bool
    name: str


def parse_record(data: bytes, offset: int) -> tuple[IsoEntry | None, int]:
    if offset < 0 or offset >= len(data):
        raise IsoFormatError(f"Invalid directory offset: {offset}")

    length = data[offset]
    if length == 0:
        return None, 0
    if length < 34 or offset + length > len(data):
        raise IsoFormatError("Malformed ISO directory record")

    record = data[offset : offset + length]
    name_length = record[32]
    if 33 + name_length > len(record):
        raise IsoFormatError("Malformed ISO file identifier")

    raw_name = record[33 : 33 + name_length]
    if raw_name == b"\x00":
        name = "."
    elif raw_name == b"\x01":
        name = ".."
    else:
        name = raw_name.decode("ascii", "replace").split(";", 1)[0]

    return (
        IsoEntry(
            extent=struct.unpack_from("<I", record, 2)[0],
            size=struct.unpack_from("<I", record, 10)[0],
            is_directory=bool(record[25] & 2),
            name=name,
        ),
        length,
    )


def find_primary_volume_descriptor(data: bytes) -> bytes:
    for sector in range(16, 64):
        offset = sector * SECTOR_SIZE
        if offset + SECTOR_SIZE > len(data):
            break
        if data[offset + 1 : offset + 6] == b"CD001" and data[offset] == 1:
            return data[offset : offset + SECTOR_SIZE]
    raise IsoFormatError("ISO 9660 primary volume descriptor not found")


def iter_children(data: bytes, directory: IsoEntry) -> Iterable[IsoEntry]:
    start = directory.extent * SECTOR_SIZE
    end = start + directory.size
    if start < 0 or end > len(data):
        raise IsoFormatError(f"Directory {directory.name} exceeds image bounds")

    position = start
    while position < end:
        entry, length = parse_record(data, position)
        if length == 0:
            position = ((position // SECTOR_SIZE) + 1) * SECTOR_SIZE
            continue
        position += length
        if entry is not None and entry.name not in {".", ".."}:
            yield entry


def find_path(data: bytes, path: str) -> IsoEntry:
    descriptor = find_primary_volume_descriptor(data)
    root, _ = parse_record(descriptor, 156)
    if root is None or not root.is_directory:
        raise IsoFormatError("ISO root directory is missing")

    current = root
    for part in [part for part in path.replace("\\", "/").split("/") if part]:
        if not current.is_directory:
            raise IsoFormatError(f"{current.name} is not a directory")
        match = next(
            (entry for entry in iter_children(data, current) if entry.name.casefold() == part.casefold()),
            None,
        )
        if match is None:
            raise FileNotFoundError(f"Path not found in ISO: {path} (missing {part})")
        current = match
    return current


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract UW1 strings.pak from GOG's game.gog ISO image"
    )
    parser.add_argument("image", type=Path, help="Path to game.gog")
    parser.add_argument("output", type=Path, help="Output path for strings.pak")
    parser.add_argument(
        "--path",
        default="UW/DATA/STRINGS.PAK",
        help="ISO path to extract (default: UW/DATA/STRINGS.PAK)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        data = args.image.read_bytes()
        entry = find_path(data, args.path)
        if entry.is_directory:
            raise IsoFormatError(f"Target is a directory: {args.path}")

        start = entry.extent * SECTOR_SIZE
        payload = data[start : start + entry.size]
        if len(payload) != entry.size:
            raise IsoFormatError("Target file exceeds image bounds")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        print(
            f"path={args.path}\n"
            f"size={len(payload)}\n"
            f"sha256={hashlib.sha256(payload).hexdigest()}\n"
            f"output={args.output}"
        )
        return 0
    except (OSError, IsoFormatError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
