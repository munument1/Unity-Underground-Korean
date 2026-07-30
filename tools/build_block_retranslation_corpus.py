#!/usr/bin/env python3
"""Join extracted English blocks with the current Korean global map.

Unlike the old English-keyed map, the output preserves every block/string location so
identical English text can receive different Korean translations when context requires it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


BLOCK_FILE_RE = re.compile(r"^block_(\d+)(?:_[^.]+)?\.json$", re.IGNORECASE)


class CorpusError(ValueError):
    pass


def load_global_map(path: Path) -> dict[str, str]:
    root = json.loads(path.read_text(encoding="utf-8"))
    mapping = root.get("99999")
    if not isinstance(mapping, dict):
        raise CorpusError(f"{path}: 99999 object was not found")
    return {str(source): str(translated) for source, translated in mapping.items()}


def load_extracted_blocks(directory: Path) -> list[dict[str, object]]:
    if not directory.is_dir():
        raise CorpusError(f"Block directory was not found: {directory}")

    occurrences: list[dict[str, object]] = []
    seen_locations: set[tuple[int, int]] = set()
    files = sorted(path for path in directory.iterdir() if path.is_file())

    for path in files:
        match = BLOCK_FILE_RE.match(path.name)
        if not match:
            continue
        filename_block_id = int(match.group(1))
        root = json.loads(path.read_text(encoding="utf-8"))
        if len(root) != 1:
            raise CorpusError(f"{path}: expected exactly one block object")
        block_key, entries = next(iter(root.items()))
        try:
            block_id = int(block_key)
        except ValueError as exc:
            raise CorpusError(f"{path}: non-numeric block key {block_key!r}") from exc
        if block_id != filename_block_id:
            raise CorpusError(
                f"{path}: filename block {filename_block_id} != JSON block {block_id}"
            )
        if not isinstance(entries, dict):
            raise CorpusError(f"{path}: block value must be an object")

        numeric_entries: list[tuple[int, str]] = []
        for string_key, value in entries.items():
            try:
                string_id = int(string_key)
            except ValueError as exc:
                raise CorpusError(
                    f"{path}: non-numeric string ID {string_key!r}"
                ) from exc
            if not isinstance(value, str):
                raise CorpusError(
                    f"{path}: block {block_id}, string {string_id} is not text"
                )
            numeric_entries.append((string_id, value))

        numeric_entries.sort()
        expected_ids = list(range(len(numeric_entries)))
        actual_ids = [string_id for string_id, _ in numeric_entries]
        if actual_ids != expected_ids:
            raise CorpusError(
                f"{path}: string IDs must be contiguous from 0; got "
                f"{actual_ids[:10]}{'...' if len(actual_ids) > 10 else ''}"
            )

        for string_id, source in numeric_entries:
            location = (block_id, string_id)
            if location in seen_locations:
                raise CorpusError(f"Duplicate location: block {block_id}, string {string_id}")
            seen_locations.add(location)
            occurrences.append(
                {
                    "blockId": block_id,
                    "stringId": string_id,
                    "source": source,
                    "sourceFile": path.name,
                }
            )

    if not occurrences:
        raise CorpusError(f"No block_*.json files were found in {directory}")
    occurrences.sort(key=lambda entry: (int(entry["blockId"]), int(entry["stringId"])))
    return occurrences


def build_corpus(
    occurrences: list[dict[str, object]], global_map: dict[str, str]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    source_counts = Counter(
        str(entry["source"]) for entry in occurrences if str(entry["source"])
    )
    locations_by_source: dict[str, list[dict[str, int]]] = defaultdict(list)
    for entry in occurrences:
        source = str(entry["source"])
        if source:
            locations_by_source[source].append(
                {
                    "blockId": int(entry["blockId"]),
                    "stringId": int(entry["stringId"]),
                }
            )

    corpus: list[dict[str, object]] = []
    matched_occurrences = 0
    nonempty_occurrences = 0
    missing_sources: set[str] = set()

    for entry in occurrences:
        source = str(entry["source"])
        current = global_map.get(source, "") if source else ""
        if source:
            nonempty_occurrences += 1
            if source in global_map:
                matched_occurrences += 1
            else:
                missing_sources.add(source)
        corpus.append(
            {
                **entry,
                "currentTranslation": current,
                "duplicateSourceCount": source_counts.get(source, 0),
            }
        )

    extracted_unique_sources = set(locations_by_source)
    extra_global_sources = sorted(set(global_map) - extracted_unique_sources)
    duplicate_sources = [
        {
            "source": source,
            "occurrenceCount": len(locations),
            "locations": locations,
        }
        for source, locations in sorted(locations_by_source.items())
        if len(locations) > 1
    ]

    report: dict[str, object] = {
        "occurrenceCount": len(occurrences),
        "nonEmptyOccurrenceCount": nonempty_occurrences,
        "uniqueSourceCount": len(extracted_unique_sources),
        "globalMapSourceCount": len(global_map),
        "matchedOccurrenceCount": matched_occurrences,
        "missingUniqueSourceCount": len(missing_sources),
        "extraGlobalSourceCount": len(extra_global_sources),
        "duplicateUniqueSourceCount": len(duplicate_sources),
        "missingSources": sorted(missing_sources),
        "extraGlobalSources": extra_global_sources,
        "duplicateSources": duplicate_sources,
    }
    return corpus, report


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a block-aware retranslation corpus from extracted English"
    )
    parser.add_argument(
        "--blocks",
        type=Path,
        default=Path("tools/output/english_source/blocks"),
        help="Directory containing extracted block_*.json files",
    )
    parser.add_argument(
        "--global-map",
        type=Path,
        default=Path("translations/global_text_map.json"),
        help="Current English-keyed Korean translation map",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tools/output/block_retranslation_corpus.json"),
        help="Location-preserving corpus output",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("tools/output/block_source_comparison.json"),
        help="Coverage and duplicate-source report",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        occurrences = load_extracted_blocks(args.blocks)
        global_map = load_global_map(args.global_map)
        corpus, report = build_corpus(occurrences, global_map)
        write_json(args.output, corpus)
        write_json(args.report, report)
        print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, CorpusError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
