#!/usr/bin/env python3
"""Create AI/manual retranslation batches from the block-aware corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


class BatchError(ValueError):
    pass


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_entry(block_id: int, entry: dict[str, object]) -> dict[str, object]:
    return {
        "blockId": block_id,
        "stringId": entry["stringId"],
        "source": entry["displaySource"],
        "rawSource": entry["rawSource"],
        "currentTranslation": entry["currentTranslation"],
        "proposedTranslation": "",
        "reviewNotes": "",
        "matchMethod": entry["matchMethod"],
        "duplicateSourceCount": entry["duplicateSourceCount"],
        "contextBefore": entry["contextBefore"],
        "contextAfter": entry["contextAfter"],
    }


def split_entries(entries: list[dict[str, object]], limit: int) -> list[list[dict[str, object]]]:
    batches: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    size = 0
    for entry in entries:
        next_size = len(json.dumps(entry, ensure_ascii=False)) + 1
        if current and size + next_size > limit:
            batches.append(current)
            current = []
            size = 0
        current.append(entry)
        size += next_size
    if current:
        batches.append(current)
    return batches


def category(block_id: int) -> str:
    if block_id >= 3000:
        return "dialogue_or_cutscene"
    if block_id in {3, 24}:
        return "lore_notes_or_debug"
    if block_id in {4, 5, 6, 7, 8, 9, 10}:
        return "terms_items_spells"
    return "system_or_ui"


def instructions_for(category_name: str) -> list[str]:
    common = [
        "Ultima Underworld 1의 영문 원문을 자연스러운 한국어로 재번역한다.",
        "currentTranslation은 참고만 하고 오역·직역·말투 혼용을 답습하지 않는다.",
        "blockId, stringId, rawSource, source는 변경하지 않는다.",
        "printf 토큰, @SS1 같은 게임 토큰, 역슬래시 제어 코드와 줄바꿈의 기능을 보존한다.",
        "완료한 한국어는 proposedTranslation에 쓰고 판단 근거가 필요한 경우 reviewNotes에 짧게 적는다.",
    ]
    if category_name == "dialogue_or_cutscene":
        return common + [
            "블록 전체를 한 대화 문맥으로 읽고 화자·응답 관계·감정·종족 말투를 일관되게 유지한다.",
            "thou/thee가 있다는 이유만으로 무조건 고풍체를 쓰지 않는다.",
            "플레이어 선택지는 기본적으로 자연스러운 중립체로 쓰되 모욕·위협 선택지는 의도대로 거칠게 쓴다.",
        ]
    if category_name == "terms_items_spells":
        return common + [
            "아이템·기술·주문은 문장보다 용어 통일을 우선한다.",
            "Great, Very Great, Tremendous, Unsurpassed 같은 단계 표현을 단어별로 직역하지 않는다.",
        ]
    return common + [
        "시스템 안내는 간결한 문장으로, 버튼·상태명은 명사형으로 쓴다.",
        "동적 문장 조각은 단독 문장보다 실제 결합 결과가 자연스럽도록 번역한다.",
    ]


def build_batches(corpus: dict[str, object], character_limit: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    raw_blocks = corpus.get("blocks")
    if not isinstance(raw_blocks, list):
        raise BatchError("Corpus blocks array was not found")
    batches: list[dict[str, object]] = []
    block_manifest: list[dict[str, object]] = []
    total_entries = 0

    for block in raw_blocks:
        if not isinstance(block, dict) or not isinstance(block.get("entries"), list):
            raise BatchError("Malformed corpus block")
        block_id = int(block["blockId"])
        entries = [
            compact_entry(block_id, entry)
            for entry in block["entries"]
            if isinstance(entry, dict) and str(entry.get("rawSource", ""))
        ]
        if not entries:
            continue
        total_entries += len(entries)
        category_name = category(block_id)
        parts = [entries] if block_id >= 3000 else split_entries(entries, character_limit)
        part_files: list[str] = []
        for part_index, part in enumerate(parts, start=1):
            suffix = f"_part{part_index:02d}" if len(parts) > 1 else ""
            filename = f"block_{block_id:04d}{suffix}.json"
            payload = {
                "schemaVersion": 1,
                "category": category_name,
                "blockId": block_id,
                "part": part_index,
                "partCount": len(parts),
                "sourceFile": block.get("sourceFile"),
                "instructions": instructions_for(category_name),
                "entries": part,
            }
            batches.append({"file": filename, "payload": payload})
            part_files.append(filename)
        block_manifest.append({
            "blockId": block_id,
            "category": category_name,
            "entryCount": len(entries),
            "partCount": len(parts),
            "files": part_files,
        })

    manifest = {
        "schemaVersion": 1,
        "entryCount": total_entries,
        "batchFileCount": len(batches),
        "sourceBlockCount": len(block_manifest),
        "characterLimitForNonDialogue": character_limit,
        "dialogueBlocksKeptWhole": True,
        "blocks": block_manifest,
    }
    return batches, manifest


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build block-preserving retranslation batches")
    p.add_argument("corpus", type=Path)
    p.add_argument("output_dir", type=Path)
    p.add_argument("--character-limit", type=int, default=24000)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.character_limit < 1000:
            raise BatchError("--character-limit must be at least 1000")
        corpus = read_json(args.corpus)
        if not isinstance(corpus, dict):
            raise BatchError("Corpus root must be an object")
        batches, manifest = build_batches(corpus, args.character_limit)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for old in args.output_dir.glob("block_*.json"):
            old.unlink()
        for batch in batches:
            write_json(args.output_dir / str(batch["file"]), batch["payload"])
        write_json(args.output_dir / "manifest.json", manifest)
        print(json.dumps({k: v for k, v in manifest.items() if k != "blocks"}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, BatchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
