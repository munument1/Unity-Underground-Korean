# 블록별 재번역 코퍼스 생성 결과

Ultima Underworld 1 원본 `strings.pak`에서 추출한 영문 블록과 현재 한국어 번역을 결합해, `(blockId, stringId)` 위치를 보존하는 재번역 코퍼스를 생성했습니다.

## 원문 규모

- 원문 블록: 122개
- 전체 문자열 슬롯: 10,984개
- 빈 슬롯: 3,893개
- 실제 영문 문자열 위치: 7,091개
- 고유 영문 원문: 5,037개
- 두 곳 이상에서 반복되는 고유 원문: 615개

빈 슬롯도 문자열 ID이므로 삭제하거나 앞으로 당기지 않습니다.

## 현재 번역 대응 결과

- 전역 맵 정확 일치: 6,670개
- 공백·줄바꿈·따옴표 정규화 후 일치: 383개
- 블록 위치를 사용한 동적 문장 조각: 38개
- 대응하지 못한 실제 영문: 0개

38개의 블록 위치 보완 항목은 `You are `, `You have advanced in `처럼 실행 중 다른 문자열과 조합되는 문장 조각입니다. 현재 번역에는 `%s`가 들어간 완성형 템플릿으로 보관되어 있어 전역 영어 키만으로는 대응할 수 없습니다.

## 두 종류의 영문 원문

코퍼스에는 다음 값을 함께 저장합니다.

- `rawSource`: 원본 `strings.pak`의 실제 문자열. 기존 `global_text_map.json` 조회에 사용합니다.
- `displaySource`: Unity Underground가 따옴표와 원문 오탈자를 보정한 뒤 표시하는 문자열. 재번역 시 이 값을 읽습니다.

예를 들어 원문의 줄바꿈, `\m`, 곧은따옴표 때문에 전역 맵 키와 화면 표시문이 달라질 수 있습니다. 둘을 하나로 덮어쓰면 기존 번역을 정확히 연결할 수 없으므로 별도로 유지합니다.

## 중복 원문 처리

기존 전역 맵은 영어 문장을 키로 사용하므로 같은 영어 문장은 항상 하나의 한국어로 합쳐집니다. 새 코퍼스는 모든 위치를 독립적으로 보존합니다.

```json
{
  "blockId": 3585,
  "stringId": 24,
  "displaySource": "Hast thou returned to torment me further?",
  "currentTranslation": "나를 더 괴롭히려고 돌아온 것인가?"
}
```

NPC 대사는 블록 전체를 함께 읽고, 동일한 영어라도 화자와 상황이 다르면 서로 다른 한국어를 사용할 수 있습니다.

## 생성 명령

원문은 보정 전·후 두 번 추출합니다.

```bash
python tools/extract_strings_pak.py data/strings.pak tools/output/english_raw --raw
python tools/extract_strings_pak.py data/strings.pak tools/output/english_display
```

현재 파일별 한국어 내보내기와 전역 맵을 함께 사용해 코퍼스를 만듭니다.

```bash
python tools/build_block_retranslation_corpus.py \
  --raw-blocks tools/output/english_raw/blocks \
  --display-blocks tools/output/english_display/blocks \
  --current-blocks tools/input/current_by_file_json \
  --global-map translations/global_text_map.json \
  --output tools/output/block_retranslation_corpus.json \
  --report tools/output/block_source_comparison.json \
  --by-block-output-dir tools/output/block_retranslation_by_block
```

생성물은 원작 영문 전체를 포함하므로 저장소에 커밋하지 않고 `tools/output`에서만 관리합니다.
