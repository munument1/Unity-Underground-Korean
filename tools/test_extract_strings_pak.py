#!/usr/bin/env python3
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from extract_strings_pak import PakFormatError, parse_strings_pak, write_outputs


def encode_node(char: str, left: int = 0xFF, right: int = 0xFF) -> int:
    return ord(char) | (left << 16) | (right << 24)


def build_fixture() -> bytes:
    # Codes: A=00, B=01, terminator=1. Each string starts byte-aligned.
    nodes = [
        encode_node("A"),
        encode_node("B"),
        encode_node("|"),
        encode_node("?", 0, 1),
        encode_node("?", 3, 2),
    ]
    header = struct.pack("<H", len(nodes))
    header += b"".join(struct.pack("<I", node) for node in nodes)
    header += struct.pack("<H", 1)
    block_offset = len(header) + 6
    header += struct.pack("<Hi", 1, block_offset)

    compressed = bytes((0x20, 0x18, 0x80))  # A, AB, empty
    block = struct.pack("<H", 3)
    block += struct.pack("<HHH", 0, 1, 2)
    block += compressed
    return header + block


class StringsPakExtractorTests(unittest.TestCase):
    def test_extracts_blocks_and_preserves_empty_ids(self) -> None:
        blocks, metadata = parse_strings_pak(build_fixture())
        self.assertEqual(blocks, {1: ["A", "AB", ""]})
        self.assertEqual(metadata["blockCount"], 1)
        self.assertEqual(metadata["stringCount"], 3)

    def test_writes_repository_compatible_json(self) -> None:
        blocks, metadata = parse_strings_pak(build_fixture())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_outputs(output, blocks, metadata)
            text = (output / "blocks" / "block_0001_system_messages.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"0": "A"', text)
            self.assertIn('"2": ""', text)
            self.assertTrue((output / "manifest.json").is_file())

    def test_rejects_invalid_node_count(self) -> None:
        with self.assertRaises(PakFormatError):
            parse_strings_pak(b"\x00\x00")


if __name__ == "__main__":
    unittest.main()
