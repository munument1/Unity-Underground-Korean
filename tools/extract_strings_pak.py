#!/usr/bin/env python3
"""Extract Ultima Underworld strings.pak into block-preserving JSON files.

The format was reconstructed from Unity Underground's StringLoader/Stream IL:
- little-endian Huffman node table
- block ID -> absolute file offset directory
- per-block string offset directory
- MSB-first bit stream terminated by the '|' leaf
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("'till ", "'til "),
    ("'the ", "‘the "),
    ("'Folanae", "‘Folanae"),
    ("'E'", "‘E'"),
    ("'W'", "‘W'"),
    (" -- ", "—"),
    (" - ", "—"),
    (r"\m", ""),
    ("  ", " "),
    (r"\p", "\n"),
    ("`Tis", "'Tis"),
    (" tis ", " 'tis "),
    ("partake from", "partake of"),
    ("Volcanos:", "Volcanoes:"),
    ("splahes", "splashes"),
    ("Enscribed", "Inscribed"),
    (" . . . . .", "..."),
    (" . . .", "..."),
    (". . .", "..."),
    (" ...", "..."),
    ("twelveth", "twelfth"),
    ("tommorrow", "tomorrow"),
    ("to lead a chamber", "to lead to a chamber"),
    ("servicable", "serviceable"),
    ("by using fountain", "by drinking from the fountain"),
    ("Constuction", "Construction"),
    ("Invisibilty", "Invisibility"),
    ("Abyss' ", "Abyss's "),
    ("Cabirus' ", "Cabirus's "),
    ("the Book of Honesty.\n", "the Book of Honesty"),
    ("the Taper of Sacrifice.\n", "the Taper of Sacrifice"),
    ("the Wine of Compassion.\n", "the Wine of Compassion"),
    ("the Standard of Honor.\n", "the Standard of Honor"),
    ("the Shield of Valor.\n", "the Shield of Valor"),
    ("the Cup of Wonder.\n", "the Cup of Wonder"),
    ("the Sword of Justice.\n", "the Sword of Justice"),
    ("the Ring of Humility.\n", "the Ring of Humility"),
)

BLOCK_LABELS: dict[int, str] = {
    1: "system_messages",
    2: "character_creation",
    3: "scrolls_and_notes",
    4: "item_names",
    5: "item_condition",
    7: "classes_and_professions",
    8: "skills_and_stats",
    9: "monster_names",
    10: "level_names",
}


class PakFormatError(ValueError):
    pass


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.buffer = 0
        self.buffer_bits = 0

    def _need(self, count: int) -> None:
        if self.pos < 0 or self.pos + count > len(self.data):
            raise PakFormatError(
                f"Unexpected end of file at 0x{self.pos:X}; need {count} bytes"
            )

    def read_u8(self) -> int:
        self._need(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def read_u16(self) -> int:
        self._need(2)
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def read_i32(self) -> int:
        self._need(4)
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def read_u32(self) -> int:
        self._need(4)
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise PakFormatError(f"Invalid absolute seek offset 0x{offset:X}")
        self.pos = offset
        self.buffer = 0
        self.buffer_bits = 0

    def read_upper_bit(self) -> int:
        self.buffer_bits -= 1
        if self.buffer_bits < 0:
            self.buffer = ((self.buffer << 8) | self.read_u8()) & 0xFFFF
            self.buffer_bits += 8
        return (self.buffer >> (self.buffer_bits & 31)) & 1


@dataclass(slots=True)
class HuffNode:
    char_code: int
    left_index: int | None
    right_index: int | None

    @property
    def is_leaf(self) -> bool:
        return self.left_index is None


def apply_game_fixups(value: str) -> str:
    """Match StringLoader.FixUpQuotesAndErrors from the 28 Jul 2026 build."""
    if not value:
        return value
    for old, new in REPLACEMENTS:
        value = value.replace(old, new)

    output: list[str] = []
    closing_quote = False
    for char in value:
        if char == '"':
            output.append("”" if closing_quote else "“")
            closing_quote = not closing_quote
        elif char == "'":
            output.append("’")
        else:
            output.append(char)
    return "".join(output)


def decode_string(reader: Reader, nodes: list[HuffNode], max_chars: int) -> str:
    root_index = len(nodes) - 1
    node_index = root_index
    chars: list[str] = []

    while True:
        node = nodes[node_index]
        while not node.is_leaf:
            next_index = node.right_index if reader.read_upper_bit() else node.left_index
            if next_index is None or not 0 <= next_index < len(nodes):
                raise PakFormatError("Huffman tree contains an invalid child index")
            node_index = next_index
            node = nodes[node_index]

        if node.char_code == ord("|"):
            return "".join(chars)

        chars.append(chr(node.char_code))
        if len(chars) > max_chars:
            raise PakFormatError(
                f"Decoded string exceeded safety limit of {max_chars} characters"
            )
        node_index = root_index


def parse_strings_pak(
    data: bytes,
    *,
    apply_fixups: bool = True,
    max_nodes: int = 512,
    max_blocks: int = 16384,
    max_strings_per_block: int = 65535,
    max_chars_per_string: int = 1_000_000,
) -> tuple[dict[int, list[str]], dict[str, object]]:
    reader = Reader(data)

    node_count = reader.read_u16()
    if not 1 <= node_count <= max_nodes:
        raise PakFormatError(f"Implausible Huffman node count: {node_count}")

    encoded_nodes = [reader.read_u32() for _ in range(node_count)]
    nodes: list[HuffNode] = []
    for value in encoded_nodes:
        left = (value >> 16) & 0xFF
        right = (value >> 24) & 0xFF
        nodes.append(
            HuffNode(
                char_code=value & 0xFF,
                left_index=left if left < node_count else None,
                right_index=right if right < node_count else None,
            )
        )

    root = nodes[-1]
    if root.is_leaf:
        raise PakFormatError("Last Huffman node is not an internal root node")

    block_count = reader.read_u16()
    if not 1 <= block_count <= max_blocks:
        raise PakFormatError(f"Implausible block count: {block_count}")

    directory: list[tuple[int, int]] = []
    for _ in range(block_count):
        block_id = reader.read_u16()
        block_offset = reader.read_i32()
        if block_offset < 0 or block_offset >= len(data):
            raise PakFormatError(
                f"Block {block_id} has invalid offset 0x{block_offset:X}"
            )
        directory.append((block_id, block_offset))

    if len({block_id for block_id, _ in directory}) != len(directory):
        raise PakFormatError("Duplicate block IDs found in directory")

    blocks: dict[int, list[str]] = {}
    raw_nonempty = 0
    fixed_nonempty = 0
    total_strings = 0

    for block_id, block_offset in directory:
        reader.seek(block_offset)
        string_count = reader.read_u16()
        if string_count > max_strings_per_block:
            raise PakFormatError(
                f"Block {block_id} has implausible string count: {string_count}"
            )
        offsets = [reader.read_u16() for _ in range(string_count)]
        data_start = reader.pos
        values: list[str] = []

        for index, relative_offset in enumerate(offsets):
            absolute_offset = data_start + relative_offset
            if absolute_offset >= len(data):
                raise PakFormatError(
                    f"Block {block_id}, string {index} has invalid offset "
                    f"0x{absolute_offset:X}"
                )
            reader.seek(absolute_offset)
            raw = decode_string(reader, nodes, max_chars=max_chars_per_string)
            raw_nonempty += bool(raw)
            value = apply_game_fixups(raw) if apply_fixups else raw
            fixed_nonempty += bool(value)
            values.append(value)

        blocks[block_id] = values
        total_strings += string_count

    metadata: dict[str, object] = {
        "format": "Ultima Underworld strings.pak",
        "endianness": "little",
        "huffmanBitOrder": "most-significant-bit first",
        "huffmanNodeCount": node_count,
        "blockCount": block_count,
        "stringCount": total_strings,
        "nonEmptyStringCountBeforeFixups": raw_nonempty,
        "nonEmptyStringCountAfterFixups": fixed_nonempty,
        "fixupsApplied": apply_fixups,
        "sha256": hashlib.sha256(data).hexdigest(),
        "fileSize": len(data),
    }
    return blocks, metadata


def block_filename(block_id: int) -> str:
    suffix = BLOCK_LABELS.get(block_id)
    return (
        f"block_{block_id:04d}_{suffix}.json"
        if suffix
        else f"block_{block_id:04d}.json"
    )


def write_outputs(
    output_dir: Path,
    blocks: dict[int, list[str]],
    metadata: dict[str, object],
) -> None:
    blocks_dir = output_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    block_manifest: list[dict[str, object]] = []
    for block_id in sorted(blocks):
        values = blocks[block_id]
        filename = block_filename(block_id)
        payload = {str(block_id): {str(i): value for i, value in enumerate(values)}}
        (blocks_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        block_manifest.append(
            {
                "blockId": block_id,
                "file": f"blocks/{filename}",
                "stringCount": len(values),
                "nonEmptyStringCount": sum(bool(value) for value in values),
            }
        )

    manifest = {**metadata, "blocks": block_manifest}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract block-preserving JSON from Ultima Underworld data/strings.pak"
    )
    parser.add_argument("input", type=Path, help="Path to data/strings.pak")
    parser.add_argument("output", type=Path, help="Output directory")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Do not apply Unity Underground's quote and typo fixups",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Parse and validate without writing block files",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = args.input.read_bytes()
        blocks, metadata = parse_strings_pak(data, apply_fixups=not args.raw)
        if not args.verify_only:
            write_outputs(args.output, blocks, metadata)
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0
    except (OSError, PakFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
