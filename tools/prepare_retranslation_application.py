#!/usr/bin/env python3
"""Repair completed bundle JSON and prepare the final application tool."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

INVALID_CONTROL_RE = re.compile(r"(?<!\\)\\(?=[mp0-9])")


def repair_bundles(directory: Path) -> list[str]:
    repaired_files: list[str] = []
    paths = sorted(directory.glob("bundle_*_translations.json"))
    if len(paths) != 33:
        raise RuntimeError(f"Expected 33 bundle files, found {len(paths)}")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        repaired = INVALID_CONTROL_RE.sub(lambda match: "\\" + match.group(0), text)
        json.loads(repaired)
        if repaired != text:
            path.write_text(repaired, encoding="utf-8")
            repaired_files.append(str(path))
    return repaired_files


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Application tool patch pattern was not found: {label}")
    return text.replace(old, new, 1)


def patch_application_tool(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "def compact_source(value: str) -> str:" in text:
        return False

    text = replace_once(
        text,
        "def is_dynamic_source(source: str) -> bool:\n",
        "def compact_source(value: str) -> str:\n"
        "    return re.sub(r\"\\s+\", \"\", normalize_source(value))\n\n\n"
        "def is_dynamic_source(source: str) -> bool:\n",
        "compact-source function",
    )

    old_resolver = '''def resolve_global_key(source, global_map, normalized_index):
    if source in global_map:
        return source, "exact"
    candidates = normalized_index.get(normalize_source(source), [])
    if len(candidates) == 1:
        return candidates[0], "normalized"
    if len(candidates) > 1 and len({global_map[key] for key in candidates}) == 1:
        return sorted(candidates)[0], "normalized-equivalent"
    return None, "ambiguous-normalized" if candidates else "missing"
'''
    new_resolver = '''def resolve_global_key(source, global_map, normalized_index, compact_index):
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
'''
    text = replace_once(text, old_resolver, new_resolver, "global-key resolver")

    text = replace_once(
        text,
        "    normalized_index = defaultdict(list)\n    value_index = defaultdict(list)\n",
        "    normalized_index = defaultdict(list)\n"
        "    compact_index = defaultdict(list)\n"
        "    value_index = defaultdict(list)\n",
        "compact index declaration",
    )
    text = replace_once(
        text,
        "        normalized_index[normalize_source(key)].append(key)\n"
        "        value_index[value].append(key)\n",
        "        normalized_index[normalize_source(key)].append(key)\n"
        "        compact_index[compact_source(key)].append(key)\n"
        "        value_index[value].append(key)\n",
        "compact index population",
    )

    old_missing = '''        if source is None:
            source_missing_locations.append({"blockId": location[0], "stringId": location[1]})
            value_candidates = value_index.get(current_by_location[location], [])
            if len(value_candidates) == 1:
                key_candidates[value_candidates[0]].append((proposal, location))
                resolution_counts["current-value-unique"] += 1
            else:
                unresolved.append({
                    "blockId": location[0], "stringId": location[1],
                    "reason": "source-location-missing",
                    "candidateGlobalKeyCount": len(value_candidates),
                })
            continue
'''
    new_missing = '''        if source is None:
            source_missing_locations.append({"blockId": location[0], "stringId": location[1]})
            resolution_counts["source-missing-block-only"] += 1
            continue
'''
    text = replace_once(text, old_missing, new_missing, "missing source handling")

    text = replace_once(
        text,
        "        if is_dynamic_source(source):\n",
        "        stripped_source = TOKEN_RE.sub(\"\", source)\n"
        "        if proposal == source or not re.search(r\"[A-Za-z가-힣]\", stripped_source):\n"
        "            resolution_counts[\"literal-block-only\"] += 1\n"
        "            continue\n"
        "        if is_dynamic_source(source):\n",
        "literal source handling",
    )
    text = replace_once(
        text,
        "        global_key, method = resolve_global_key(source, global_map, normalized_index)\n",
        "        global_key, method = resolve_global_key(\n"
        "            source, global_map, normalized_index, compact_index\n"
        "        )\n",
        "resolver call",
    )

    path.write_text(text, encoding="utf-8")
    compile(text, str(path), "exec")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundles-dir", type=Path, default=Path("retranslation/completed"))
    parser.add_argument(
        "--application-tool",
        type=Path,
        default=Path("tools/apply_completed_retranslations.py"),
    )
    args = parser.parse_args()
    repaired = repair_bundles(args.bundles_dir)
    tool_changed = patch_application_tool(args.application_tool)
    print(json.dumps({
        "repairedBundleFiles": repaired,
        "applicationToolChanged": tool_changed,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
