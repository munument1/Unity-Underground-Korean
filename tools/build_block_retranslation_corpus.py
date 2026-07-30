#!/usr/bin/env python3
"""Build a block-aware Unity Underground retranslation corpus.

English strings are read twice from UW1 strings.pak exports:
- raw blocks preserve the exact lookup keys used by the existing global map;
- display blocks apply Unity Underground's runtime quote/typo fixups.

Current Korean is matched in this order:
1. exact raw English key in global_text_map.json;
2. a unique normalized English key in global_text_map.json;
3. the existing Korean value at the same (blockId, stringId), used mainly for
   dynamic sentence fragments deliberately omitted from the global map.

The output always preserves every (blockId, stringId), so duplicate English
sentences can be retranslated differently when context requires it.
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
KOREAN_RE = re.compile(r"[가-힣]")


class CorpusError(ValueError):
    pass


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def block_files(directory: Path) -> dict[int, Path]:
    if not directory.is_dir():
        raise CorpusError(f"Block directory was not found: {directory}")
    result: dict[int, Path] = {}
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = BLOCK_FILE_RE.match(path.name)
        if not match:
            continue
        block_id = int(match.group(1))
        if block_id in result:
            raise CorpusError(f"Duplicate block ID {block_id} in {directory}")
        result[block_id] = path
    if not result:
        raise CorpusError(f"No block_*.json files were found in {directory}")
    return result


def load_source_blocks(directory: Path) -> tuple[dict[tuple[int, int], str], dict[int, str]]:
    locations: dict[tuple[int, int], str] = {}
    filenames: dict[int, str] = {}
    for filename_block_id, path in sorted(block_files(directory).items()):
        root = read_json(path)
        if not isinstance(root, dict) or len(root) != 1:
            raise CorpusError(f"{path}: expected exactly one block object")
        block_key, entries = next(iter(root.items()))
        try:
            block_id = int(block_key)
        except ValueError as exc:
            raise CorpusError(f"{path}: non-numeric block key {block_key!r}") from exc
        if block_id != filename_block_id:
            raise CorpusError(f"{path}: filename block {filename_block_id} != JSON block {block_id}")
        if not isinstance(entries, dict):
            raise CorpusError(f"{path}: block value must be an object")
        filenames[block_id] = path.name
        ids: list[int] = []
        for string_key, value in entries.items():
            try:
                string_id = int(string_key)
            except ValueError as exc:
                raise CorpusError(f"{path}: non-numeric string ID {string_key!r}") from exc
            if not isinstance(value, str):
                raise CorpusError(f"{path}: block {block_id}, string {string_id} is not text")
            location = (block_id, string_id)
            if location in locations:
                raise CorpusError(f"Duplicate source location {location}")
            locations[location] = value
            ids.append(string_id)
        if sorted(ids) != list(range(len(ids))):
            raise CorpusError(f"{path}: string IDs must be contiguous from 0")
    return locations, filenames


def load_current_blocks(
    directory: Path | None, allowed_block_ids: set[int]
) -> tuple[dict[tuple[int, int], str], dict[int, str]]:
    if directory is None:
        return {}, {}
    locations: dict[tuple[int, int], str] = {}
    filenames: dict[int, str] = {}
    for block_id, path in sorted(block_files(directory).items()):
        filenames[block_id] = path.name
        if block_id not in allowed_block_ids:
            continue
        root = read_json(path)
        if not isinstance(root, dict) or len(root) != 1:
            raise CorpusError(f"{path}: expected exactly one block object")
        block_key, entries = next(iter(root.items()))
        if int(block_key) != block_id or not isinstance(entries, dict):
            raise CorpusError(f"{path}: malformed block object")
        for string_key, value in entries.items():
            try:
                string_id = int(string_key)
            except ValueError as exc:
                raise CorpusError(f"{path}: non-numeric string ID {string_key!r}") from exc
            if isinstance(value, str):
                text = value
            elif isinstance(value, dict) and isinstance(value.get("kr"), str):
                text = value["kr"]
            else:
                raise CorpusError(f"{path}: string {string_id} has no string kr value")
            locations[(block_id, string_id)] = text
    return locations, filenames


def load_global_map(path: Path) -> dict[str, str]:
    root = read_json(path)
    if not isinstance(root, dict) or not isinstance(root.get("99999"), dict):
        raise CorpusError(f"{path}: 99999 object was not found")
    return {str(k): str(v) for k, v in root["99999"].items()}


def normalize_source(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    value = value.translate(
        str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-"})
    )
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", value)


def normalized_global_index(global_map: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for source, translation in global_map.items():
        index[normalize_source(source)].append((source, translation))
    return index


def classify(source: str, current: str) -> str:
    if not source:
        return "empty-source"
    if not current:
        return "missing-translation"
    if current == source:
        return "unchanged"
    if KOREAN_RE.search(current):
        return "translated"
    return "non-korean-translation"


def translation_for(
    location: tuple[int, int],
    raw_source: str,
    global_map: dict[str, str],
    normalized_index: dict[str, list[tuple[str, str]]],
    current_by_location: dict[tuple[int, int], str],
) -> tuple[str, str, str | None]:
    if not raw_source:
        return "", "empty-source", None
    if raw_source in global_map:
        return global_map[raw_source], "global-map-exact", raw_source
    candidates = normalized_index.get(normalize_source(raw_source), [])
    translations = {translation for _, translation in candidates}
    if candidates and len(translations) == 1:
        return next(iter(translations)), "global-map-normalized", candidates[0][0]
    if location in current_by_location:
        return current_by_location[location], "block-location-fallback", None
    return "", "missing", None


def build_corpus(
    raw_sources: dict[tuple[int, int], str],
    display_sources: dict[tuple[int, int], str],
    source_files: dict[int, str],
    current_by_location: dict[tuple[int, int], str],
    current_files: dict[int, str],
    global_map: dict[str, str],
) -> tuple[dict[str, object], dict[str, object]]:
    if set(raw_sources) != set(display_sources):
        only_raw = sorted(set(raw_sources) - set(display_sources))
        only_display = sorted(set(display_sources) - set(raw_sources))
        raise CorpusError(
            f"Raw/display locations differ: raw-only={only_raw[:5]}, display-only={only_display[:5]}"
        )

    normalized_index = normalized_global_index(global_map)
    source_counts = Counter(source for source in raw_sources.values() if source)
    locations_by_source: dict[str, list[dict[str, int]]] = defaultdict(list)
    for (block_id, string_id), source in sorted(raw_sources.items()):
        if source:
            locations_by_source[source].append({"blockId": block_id, "stringId": string_id})

    by_block: dict[int, list[int]] = defaultdict(list)
    for block_id, string_id in raw_sources:
        by_block[block_id].append(string_id)

    match_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    unmatched: list[dict[str, object]] = []
    normalized_matches: list[dict[str, object]] = []
    block_fallbacks: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []

    for block_id in sorted(by_block):
        ids = sorted(by_block[block_id])
        entries: list[dict[str, object]] = []
        for index, string_id in enumerate(ids):
            location = (block_id, string_id)
            raw_source = raw_sources[location]
            display_source = display_sources[location]
            current, match_method, matched_key = translation_for(
                location, raw_source, global_map, normalized_index, current_by_location
            )
            match_counts[match_method] += 1
            status = classify(raw_source, current)
            status_counts[status] += 1
            entry = {
                "stringId": string_id,
                "rawSource": raw_source,
                "displaySource": display_source,
                "currentTranslation": current,
                "matchMethod": match_method,
                "matchedGlobalKey": matched_key,
                "status": status,
                "duplicateSourceCount": source_counts.get(raw_source, 0),
                "contextBefore": [display_sources[(block_id, sid)] for sid in ids[max(0, index - 3):index]],
                "contextAfter": [display_sources[(block_id, sid)] for sid in ids[index + 1:index + 4]],
            }
            entries.append(entry)
            short = {"blockId": block_id, "stringId": string_id, "rawSource": raw_source, "currentTranslation": current}
            if match_method == "missing":
                unmatched.append(short)
            elif match_method == "global-map-normalized":
                normalized_matches.append({**short, "matchedGlobalKey": matched_key})
            elif match_method == "block-location-fallback":
                block_fallbacks.append(short)
        blocks.append({
            "blockId": block_id,
            "sourceFile": source_files[block_id],
            "currentFile": current_files.get(block_id),
            "entryCount": len(entries),
            "nonEmptySourceCount": sum(bool(entry["rawSource"]) for entry in entries),
            "entries": entries,
        })

    unique_sources = set(locations_by_source)
    extra_global_sources = sorted(set(global_map) - unique_sources)
    duplicate_sources = [
        {"source": source, "occurrenceCount": len(locations), "locations": locations}
        for source, locations in sorted(locations_by_source.items())
        if len(locations) > 1
    ]
    report: dict[str, object] = {
        "sourceBlockCount": len(source_files),
        "currentBlockCount": len(current_files),
        "commonBlockCount": len(set(source_files) & set(current_files)),
        "sourceOnlyBlockIds": sorted(set(source_files) - set(current_files)),
        "currentOnlyBlockIds": sorted(set(current_files) - set(source_files)),
        "occurrenceCount": len(raw_sources),
        "nonEmptyOccurrenceCount": sum(bool(value) for value in raw_sources.values()),
        "uniqueSourceCount": len(unique_sources),
        "globalMapSourceCount": len(global_map),
        "matchCounts": dict(sorted(match_counts.items())),
        "statusCounts": dict(sorted(status_counts.items())),
        "unmatchedCount": len(unmatched),
        "normalizedMatchCount": len(normalized_matches),
        "blockLocationFallbackCount": len(block_fallbacks),
        "extraGlobalSourceCount": len(extra_global_sources),
        "duplicateUniqueSourceCount": len(duplicate_sources),
        "unmatched": unmatched,
        "normalizedMatches": normalized_matches,
        "blockLocationFallbacks": block_fallbacks,
        "extraGlobalSources": extra_global_sources,
        "duplicateSources": duplicate_sources,
    }
    corpus = {
        "schemaVersion": 3,
        "matchingKey": ["blockId", "stringId"],
        "translationMatchOrder": [
            "global-map-exact",
            "global-map-normalized",
            "block-location-fallback",
        ],
        "blocks": blocks,
    }
    return corpus, report


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_by_block(directory: Path, corpus: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    blocks = corpus.get("blocks")
    if not isinstance(blocks, list):
        raise CorpusError("Corpus blocks are missing")
    for block in blocks:
        if not isinstance(block, dict):
            raise CorpusError("Corpus block is malformed")
        write_json(directory / str(block["sourceFile"]), block)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a block-aware retranslation corpus")
    p.add_argument("--raw-blocks", type=Path, required=True)
    p.add_argument("--display-blocks", type=Path, required=True)
    p.add_argument("--current-blocks", type=Path)
    p.add_argument("--global-map", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--by-block-output-dir", type=Path)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        raw, raw_files = load_source_blocks(args.raw_blocks)
        display, display_files = load_source_blocks(args.display_blocks)
        if raw_files.keys() != display_files.keys():
            raise CorpusError("Raw and display block IDs differ")
        current, current_files = load_current_blocks(args.current_blocks, set(raw_files))
        global_map = load_global_map(args.global_map)
        corpus, report = build_corpus(raw, display, raw_files, current, current_files, global_map)
        write_json(args.output, corpus)
        write_json(args.report, report)
        if args.by_block_output_dir:
            write_by_block(args.by_block_output_dir, corpus)
        print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, CorpusError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
