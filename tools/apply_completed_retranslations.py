#!/usr/bin/env python3
"""Apply completed block-aware retranslations to distributable translation files."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BLOCK_FILE_RE = re.compile(r"^block_(\d+)(?:_[^.]+)?\.json$", re.I)
BUNDLE_FILE_RE = re.compile(r"^bundle_(\d+)_translations\.json$", re.I)
SOURCE_LINE_RE = re.compile(r"^(\d+)=(\d+)=(.*)$")
TOKEN_RE = re.compile(r"@[A-Z]{2}(?:-?[A-Z0-9]+)?|\\(?:m|p|\d+)")

DYNAMIC_SOURCES = {
    "It looks to be that of ", "They look to be those of ",
    "You have advanced greatly in ", "You have advanced in ",
    "You cannot advance in ", "The Cup of Wonder is ",
    "You detect a creature ", "You detect a few creatures ",
    "You detect the activity of many creatures ", " is currently active.",
    "You are currently ", "You are on the ", " level of the Abyss.",
    "It is the ", " day of your imprisonment.",
    "You guess that it is currently ", "Your current vitality is ",
    "Your current mana points are ", "You are ", " poisoned.", " and ",
    " is nearly done", " is unstable", " is stable", "You destroyed the ",
    "You damaged the ", "Your attempt has no effect on the ",
    "You have partially repaired the ", "You have fully repaired the ",
    "You have attained experience level ", " tasted putrid.",
    " tasted a little rancid.", " tasted kind of bland.",
    " tasted pretty good.", " tasted great.", "A level ", "after ",
    " days in the Abyss", "You think it will be ", " to repair the ",
    "Make an attempt? ", " is angered by your action.",
    " is annoyed by your action.", " notes your action.",
    "Your Rune of Warding has been set off ", "You see ",
}


class ApplyError(RuntimeError):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_source(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    value = value.translate(str.maketrans({
        "’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-"
    }))
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", value)


def compact_source(value: str) -> str:
    return re.sub(r"\s+", "", normalize_source(value))


def is_dynamic_source(source: str) -> bool:
    return (
        source in DYNAMIC_SOURCES
        or "%s" in source
        or "{0}" in source
    )


def load_bundles(directory: Path):
    paths = []
    for path in directory.iterdir():
        match = BUNDLE_FILE_RE.match(path.name)
        if match:
            paths.append((int(match.group(1)), path))
    paths.sort()
    numbers = [number for number, _ in paths]
    if numbers != list(range(1, 34)):
        raise ApplyError(f"Expected bundles 1-33, found {numbers}")

    proposals = {}
    bundle_stats = []
    for number, path in paths:
        root = read_json(path)
        translations = root.get("translations")
        if not isinstance(translations, dict):
            raise ApplyError(f"{path}: translations object missing")
        actual_count = 0
        for block_key, entries in translations.items():
            if not isinstance(entries, dict):
                raise ApplyError(f"{path}: malformed block {block_key}")
            block_id = int(block_key)
            for string_key, value in entries.items():
                if not isinstance(value, str):
                    raise ApplyError(f"{path}: {block_id}:{string_key} is not text")
                location = (block_id, int(string_key))
                if location in proposals and proposals[location] != value:
                    raise ApplyError(f"Conflicting proposal at {location}")
                proposals[location] = value
                actual_count += 1
        if root.get("entryCount") != actual_count:
            raise ApplyError(f"{path}: entryCount mismatch")
        if root.get("validationIssueCount") != 0:
            raise ApplyError(f"{path}: validation issues remain")
        bundle_stats.append({
            "bundle": number,
            "file": path.name,
            "entryCount": actual_count,
            "changedEntryCount": root.get("changedEntryCount"),
        })
    return proposals, bundle_stats


def find_block_files(directory: Path):
    result = {}
    for path in directory.iterdir():
        match = BLOCK_FILE_RE.match(path.name)
        if not path.is_file() or not match:
            continue
        block_id = int(match.group(1))
        if block_id in result:
            raise ApplyError(f"Duplicate translation block {block_id}")
        result[block_id] = path
    return result


def load_source_list(path: Path):
    result = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = SOURCE_LINE_RE.match(line)
        if not match:
            if line.strip():
                raise ApplyError(f"{path}:{line_number}: malformed source line")
            continue
        location = (int(match.group(1)), int(match.group(2)))
        if location in result:
            raise ApplyError(f"{path}:{line_number}: duplicate location {location}")
        result[location] = match.group(3)
    return result


def resolve_global_key(source, global_map, normalized_index, compact_index):
    if source in global_map:
        return source, "exact"
    candidates = normalized_index.get(normalize_source(source), [])
    if len(candidates) == 1:
        return candidates[0], "normalized"
    if len(candidates) > 1 and len({global_map[key] for key in candidates}) == 1:
        return sorted(candidates)[0], "normalized-equivalent"
    compact_candidates = compact_index.get(compact_source(source), [])
    if len(compact_candidates) == 1:
        return compact_candidates[0], "compact"
    if len(compact_candidates) > 1 and len({global_map[key] for key in compact_candidates}) == 1:
        return sorted(compact_candidates)[0], "compact-equivalent"
    if candidates:
        return None, "ambiguous-normalized"
    return None, "ambiguous-compact" if compact_candidates else "missing"


def select_candidate(candidates, current_value):
    counts = Counter(value for value, _ in candidates)
    if len(counts) == 1:
        return next(iter(counts)), None
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top_count = ranked[0][1]
    tied = [value for value, count in ranked if count == top_count]
    if current_value in tied:
        chosen = current_value
        rule = "top-frequency-preserve-current"
    else:
        chosen = min(
            (location, value) for value, location in candidates if value in tied
        )[1]
        rule = "top-frequency-earliest-location"
    return chosen, {
        "rule": rule,
        "chosen": chosen,
        "candidateCounts": dict(ranked),
        "locations": [
            {"blockId": loc[0], "stringId": loc[1], "translation": value}
            for value, loc in sorted(candidates, key=lambda item: item[1])
        ],
    }


def apply(args):
    proposals, bundle_stats = load_bundles(args.bundles_dir)
    if len(proposals) != args.expected_count:
        raise ApplyError(
            f"Reviewed location count {len(proposals)} != expected {args.expected_count}"
        )

    block_files = find_block_files(args.translations_dir)
    source_by_location = load_source_list(args.source_list)
    global_path = args.translations_dir / "global_text_map.json"
    global_root = read_json(global_path)
    if not isinstance(global_root, dict) or not isinstance(global_root.get("99999"), dict):
        raise ApplyError("global_text_map.json: 99999 object missing")
    global_map = global_root["99999"]
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in global_map.items()):
        raise ApplyError("global map must contain string keys and values")
    original_global_count = len(global_map)

    normalized_index = defaultdict(list)
    compact_index = defaultdict(list)
    value_index = defaultdict(list)
    for key, value in global_map.items():
        normalized_index[normalize_source(key)].append(key)
        compact_index[compact_source(key)].append(key)
        value_index[value].append(key)

    block_roots = {}
    block_entries = {}
    current_by_location = {}
    for block_id in sorted({block for block, _ in proposals}):
        path = block_files.get(block_id)
        if path is None:
            raise ApplyError(f"Missing translation block file {block_id}")
        root = read_json(path)
        entries = root.get(str(block_id)) if isinstance(root, dict) else None
        if not isinstance(entries, dict):
            raise ApplyError(f"{path}: malformed block object")
        if not all(isinstance(value, str) for value in entries.values()):
            raise ApplyError(f"{path}: all entries must be strings")
        block_roots[block_id] = root
        block_entries[block_id] = entries

    for location in proposals:
        block_id, string_id = location
        key = str(string_id)
        if key not in block_entries[block_id]:
            raise ApplyError(f"Missing translation location {block_id}:{string_id}")
        current_by_location[location] = block_entries[block_id][key]

    key_candidates = defaultdict(list)
    resolution_counts = Counter()
    unresolved = []
    dynamic_skips = []
    source_missing_locations = []

    for location, proposal in sorted(proposals.items()):
        source = source_by_location.get(location)
        if source is None:
            source_missing_locations.append({"blockId": location[0], "stringId": location[1]})
            resolution_counts["source-missing-block-only"] += 1
            continue
        stripped_source = TOKEN_RE.sub("", source)
        if proposal == source or not re.search(r"[A-Za-z가-힣]", stripped_source):
            resolution_counts["literal-block-only"] += 1
            continue
        if is_dynamic_source(source):
            dynamic_skips.append({
                "blockId": location[0], "stringId": location[1],
                "source": source, "proposedTranslation": proposal,
            })
            resolution_counts["dynamic-skip"] += 1
            continue
        global_key, method = resolve_global_key(
            source, global_map, normalized_index, compact_index
        )
        if global_key is None:
            value_candidates = value_index.get(current_by_location[location], [])
            if len(value_candidates) == 1:
                global_key = value_candidates[0]
                method = "current-value-unique"
            else:
                unresolved.append({
                    "blockId": location[0], "stringId": location[1],
                    "source": source, "reason": method,
                    "candidateGlobalKeyCount": len(value_candidates),
                })
                resolution_counts[method] += 1
                continue
        key_candidates[global_key].append((proposal, location))
        resolution_counts[method] += 1

    conflicts = []
    global_updates = {}
    for key, candidates in sorted(key_candidates.items()):
        chosen, conflict = select_candidate(candidates, global_map[key])
        global_updates[key] = chosen
        if conflict:
            conflicts.append({"source": key, **conflict})

    changed_block_entries = 0
    changed_block_files = set()
    for (block_id, string_id), proposal in proposals.items():
        entries = block_entries[block_id]
        if entries[str(string_id)] != proposal:
            entries[str(string_id)] = proposal
            changed_block_entries += 1
            changed_block_files.add(block_id)

    changed_global_entries = 0
    for key, proposal in global_updates.items():
        if global_map[key] != proposal:
            global_map[key] = proposal
            changed_global_entries += 1

    validation_issues = []
    for location, proposal in proposals.items():
        block_id, string_id = location
        if block_entries[block_id][str(string_id)] != proposal:
            validation_issues.append(f"block mismatch {block_id}:{string_id}")
        source = source_by_location.get(location)
        if source is not None:
            source_tokens = Counter(TOKEN_RE.findall(source))
            proposal_tokens = Counter(TOKEN_RE.findall(proposal))
            if source_tokens != proposal_tokens:
                validation_issues.append(f"token mismatch {block_id}:{string_id}")
    if len(global_map) != original_global_count:
        validation_issues.append("global map key count changed")
    if validation_issues:
        raise ApplyError("; ".join(validation_issues[:20]))

    report = {
        "schemaVersion": 1,
        "expectedReviewedLocationCount": args.expected_count,
        "reviewedLocationCount": len(proposals),
        "bundleCount": len(bundle_stats),
        "bundleStats": bundle_stats,
        "sourceLocationCount": len(source_by_location),
        "sourceMissingLocationCount": len(source_missing_locations),
        "sourceMissingLocations": source_missing_locations,
        "changedBlockFileCount": len(changed_block_files),
        "changedBlockEntryCount": changed_block_entries,
        "globalMapKeyCount": len(global_map),
        "resolvedGlobalKeyCount": len(global_updates),
        "changedGlobalEntryCount": changed_global_entries,
        "resolutionCounts": dict(sorted(resolution_counts.items())),
        "dynamicSkipCount": len(dynamic_skips),
        "dynamicSkips": dynamic_skips,
        "unresolvedCount": len(unresolved),
        "unresolved": unresolved,
        "duplicateSourceConflictCount": len(conflicts),
        "duplicateSourceConflicts": conflicts,
        "validationIssueCount": 0,
        "validationIssues": [],
    }

    if args.max_unresolved is not None and len(unresolved) > args.max_unresolved:
        raise ApplyError(
            f"Unresolved location count {len(unresolved)} exceeds {args.max_unresolved}"
        )

    if not args.dry_run:
        for block_id in sorted(changed_block_files):
            write_json(block_files[block_id], block_roots[block_id])
        write_json(global_path, global_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundles-dir", type=Path, default=Path("retranslation/completed"))
    parser.add_argument("--translations-dir", type=Path, default=Path("translations"))
    parser.add_argument("--source-list", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--expected-count", type=int, default=7092)
    parser.add_argument("--max-unresolved", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = apply(args)
        keys = [
            "reviewedLocationCount", "sourceLocationCount",
            "sourceMissingLocationCount", "changedBlockFileCount",
            "changedBlockEntryCount", "resolvedGlobalKeyCount",
            "changedGlobalEntryCount", "dynamicSkipCount", "unresolvedCount",
            "duplicateSourceConflictCount", "validationIssueCount",
        ]
        print(json.dumps({key: report[key] for key in keys}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ValueError, ApplyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
