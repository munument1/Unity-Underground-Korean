#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build_block_retranslation_corpus.py")
spec = importlib.util.spec_from_file_location("corpus_builder", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MatchingTests(unittest.TestCase):
    def test_match_precedence_and_location_preservation(self) -> None:
        raw = {
            (1, 0): "Exact",
            (1, 1): "Trailing space ",
            (1, 2): "Dynamic fragment ",
            (1, 3): "",
        }
        display = dict(raw)
        source_files = {1: "block_0001.json"}
        current = {(1, 2): "동적 %s"}
        current_files = {1: "block_0001.json", 9999: "block_9999.json"}
        global_map = {"Exact": "정확", "Trailing space": "공백"}

        corpus, report = module.build_corpus(
            raw, display, source_files, current, current_files, global_map
        )
        entries = corpus["blocks"][0]["entries"]
        self.assertEqual(
            [entry["matchMethod"] for entry in entries],
            [
                "global-map-exact",
                "global-map-normalized",
                "block-location-fallback",
                "empty-source",
            ],
        )
        self.assertEqual(
            [entry["currentTranslation"] for entry in entries[:3]],
            ["정확", "공백", "동적 %s"],
        )
        self.assertEqual(report["unmatchedCount"], 0)
        self.assertEqual(report["currentOnlyBlockIds"], [9999])

    def test_normalized_collision_falls_back_to_location(self) -> None:
        raw = {(1, 0): "A  B"}
        display = dict(raw)
        source_files = {1: "block_0001.json"}
        current = {(1, 0): "위치 번역"}
        current_files = {1: "block_0001.json"}
        global_map = {"A B": "번역 1", " A B ": "번역 2"}

        corpus, report = module.build_corpus(
            raw, display, source_files, current, current_files, global_map
        )
        entry = corpus["blocks"][0]["entries"][0]
        self.assertEqual(entry["matchMethod"], "block-location-fallback")
        self.assertEqual(entry["currentTranslation"], "위치 번역")
        self.assertEqual(report["unmatchedCount"], 0)


if __name__ == "__main__":
    unittest.main()
