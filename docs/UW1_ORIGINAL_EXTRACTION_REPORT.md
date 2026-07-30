# Ultima Underworld 1 영문 원문 추출 결과

2026년 7월 30일 GOG 설치본의 `game.gog` ISO 이미지를 검사해 다음 파일을 확인했습니다.

```text
UW/DATA/STRINGS.PAK
```

Ultima Underworld 2 데이터도 같은 이미지의 `UW2/DATA/STRINGS.PAK`에 존재하지만, Unity Underground 재번역에는 UW1 파일만 사용합니다.

## 원본 파일 정보

- ISO 내부 경로: `UW/DATA/STRINGS.PAK`
- 파일 크기: `227,230`바이트
- SHA-256: `e8c9848a14c49620095ae180bdccbe9c6bf2942e3ad8def4a38a8a7d23004b0d`

## 블록 추출 결과

`tools/extract_strings_pak.py`로 실제 원본을 해제한 결과입니다.

- Huffman 노드: 181개
- 문자열 블록: 122개
- 전체 문자열 슬롯: 10,984개
- 비어 있지 않은 문자열: 7,091개
- 원문 그대로의 고유 비어 있지 않은 문자열: 5,033개
- 앞뒤 공백을 정규화했을 때의 고유 문자열: 5,027개

전체 슬롯 수에는 배열 위치를 보존하기 위한 빈 문자열이 포함됩니다. 동일한 대사와 거래 선택지가 여러 NPC 블록에서 반복되므로, 고유 문자열 수보다 실제 위치 수가 훨씬 많습니다.

## 확인한 주요 블록

- 블록 1: 시스템 메시지, 512슬롯 중 410개 사용
- 블록 2: 캐릭터 생성, 521슬롯 중 75개 사용
- 블록 3: 두루마리와 문서, 512슬롯 중 70개 사용
- 블록 4: 아이템 이름, 512슬롯 중 404개 사용
- 블록 3072: 도입부 컷신, 42개 모두 사용
- 블록 3585: NPC 대화, 47슬롯 중 46개 사용

## 재현 방법

GOG ISO에서 UW1 원문 파일만 꺼냅니다.

```bash
python tools/extract_strings_from_gog_iso.py \
  "D:/GOG Games/Ultima Underworld/game.gog" \
  tools/output/strings.pak
```

그다음 블록별 JSON을 생성합니다.

```bash
python tools/extract_strings_pak.py \
  tools/output/strings.pak \
  tools/output/english_source
```

## 검증

- ISO 9660 디렉터리에서 `UW/DATA/STRINGS.PAK`를 직접 추출
- 독립적으로 추출한 두 파일을 바이트 단위로 비교해 일치 확인
- 추출된 파일의 SHA-256 일치 확인
- 122개 블록 모두 Huffman 해제 완료
- 블록 ID, 문자열 ID, 빈 슬롯 보존 확인
- 블록 1의 첫 문자열 `Hey, its all the game strings`와 기존 전역 맵 원문 일치 확인

영문 원문 전체는 원작 게임 데이터이므로 저장소에 직접 커밋하지 않고, 사용자가 소유한 설치본에서 도구로 생성하는 방식을 유지합니다.
