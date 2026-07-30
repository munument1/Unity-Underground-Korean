# 영문 원문 블록 추출

Unity Underground는 번역 원문을 Unity 자산에 저장하지 않고 원작 게임 데이터의 `data/strings.pak`를 실행 중 직접 읽습니다. 2026년 7월 28일 빌드의 `Assembly-CSharp.dll`을 기준으로 `StringLoader`와 `Stream`의 동작을 역분석해, 블록 ID와 문자열 ID를 보존하는 추출기를 추가했습니다.

## 필요한 파일

다음 파일 하나만 필요합니다.

```text
<Ultima Underworld 설치 폴더>/data/strings.pak
```

Unity Underground 실행 빌드 ZIP에는 저작권이 있는 원작 데이터가 포함되지 않으므로, `UUBuild...zip`만으로는 원문 블록을 추출할 수 없습니다.

## 추출 방법

Python 3.10 이상에서 실행합니다.

```bash
python tools/extract_strings_pak.py \
  "D:/Ultima Underworld/data/strings.pak" \
  tools/output/english_source
```

Windows PowerShell에서는 한 줄로 실행해도 됩니다.

```powershell
python .\tools\extract_strings_pak.py "D:\Ultima Underworld\data\strings.pak" ".\tools\output\english_source"
```

결과 구조는 다음과 같습니다.

```text
tools/output/english_source/
├─ manifest.json
└─ blocks/
   ├─ block_0001_system_messages.json
   ├─ block_0002_character_creation.json
   ├─ block_0003_scrolls_and_notes.json
   ├─ block_0004_item_names.json
   ├─ block_0005_item_condition.json
   ├─ block_0007_classes_and_professions.json
   ├─ block_0008_skills_and_stats.json
   ├─ block_0009_monster_names.json
   ├─ block_0010_level_names.json
   └─ block_NNNN.json
```

각 파일은 다음 형식으로 저장됩니다.

```json
{
  "3585": {
    "0": "",
    "1": "Have you come to add to my pain?"
  }
}
```

빈 문자열도 삭제하지 않습니다. 배열 위치가 곧 게임의 문자열 ID이므로 빈 항목을 제거하거나 순서를 정렬하면 안 됩니다.

## 옵션

파일을 쓰지 않고 구조만 검증합니다.

```bash
python tools/extract_strings_pak.py data/strings.pak ignored --verify-only
```

Unity Underground가 실행 중 수행하는 따옴표·원문 오탈자 보정을 적용하지 않은 원시 문자열을 추출합니다.

```bash
python tools/extract_strings_pak.py data/strings.pak tools/output/english_raw --raw
```

재번역에는 기본 출력 사용을 권장합니다. 기본 출력은 게임 화면에 실제 표시되는 영문과 동일한 보정 규칙을 적용합니다.

## 복원한 파일 형식

`strings.pak`는 다음 순서로 구성됩니다.

1. 리틀 엔디언 `ushort` Huffman 노드 수
2. 노드별 `uint` 데이터
   - 하위 8비트: 문자
   - 16~23비트: 왼쪽 자식 인덱스
   - 24~31비트: 오른쪽 자식 인덱스
3. 리틀 엔디언 `ushort` 블록 수
4. 블록별 `ushort blockId`, `int absoluteOffset`
5. 각 블록의 `ushort stringCount`
6. 문자열별 `ushort relativeOffset`
7. 최상위 비트부터 읽는 Huffman 압축 문자열
8. 문자 `|` 리프를 문자열 종료 기호로 사용

추출기는 비정상 노드 수, 중복 블록 ID, 파일 범위를 벗어난 오프셋, 끝나지 않는 문자열을 오류로 처리합니다.

## 검증 상태

- Python 구문 검사 통과
- 합성 `strings.pak`으로 Huffman 해제, 블록 분리, 빈 문자열 보존 검증
- `Stream.ReadUpperBit`, `StringLoader.LoadStrings`, `GetStringBlock`, `DecompressString`, `FixUpQuotesAndErrors`의 IL 동작과 동일하게 구현

실제 원본 `strings.pak`가 확보되면 `manifest.json`의 블록 수·문자열 수와 기존 `global_text_map.json`의 5,181개 영문 키를 대조해 누락·중복 보고서를 생성합니다.
