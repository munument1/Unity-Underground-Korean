# Unity Underground 한국어 번역

Ultima Underworld의 Unity 포팅 프로젝트인 **Unity Underground**용 비공식 한국어 번역입니다.

게임 원본이나 Unity Underground 실행 파일은 포함하지 않습니다. 정상적으로 설치된 Unity Underground가 필요합니다.

## 번역 현황

**v1.1.0에서 Ultima Underworld 1 공식 영문 기준 7,092개 문자열 위치의 전체 재번역을 완료했습니다.**

- 시스템 메시지, 캐릭터 생성, 아이템, 주문, 서적, 표지판과 NPC 대화 전면 검토
- 인물별 말투, 고유명사, 퀘스트 단서와 세계관 용어 정비
- 플레이스홀더, 제어 명령, 줄바꿈과 동적 문장 구조 검증
- 149개 작업 배치 전체 완료

자세한 내용은 [`RELEASE_NOTES_v1.1.0.md`](RELEASE_NOTES_v1.1.0.md)와 [`retranslation/APPLY_REPORT.json`](retranslation/APPLY_REPORT.json)에서 확인할 수 있습니다.

## 포함 내용

- 시스템 메시지, 캐릭터 생성, 아이템, 주문, NPC 대화 한국어 번역
- 동적으로 조합되는 관찰·상태·기술 향상·수리·음식 문장의 한국어 어순 처리
- 한글 출력을 위한 BepInEx 플러그인
- 공식 영문과 위치별로 대조한 재번역 자료 및 검증 도구

## 설치

1. BepInEx 5.4.23.5를 Unity Underground에 설치합니다.
2. [Releases](https://github.com/munument1/Unity-Underground-Korean/releases)에서 최신 ZIP을 받습니다.
3. ZIP 안의 `BepInEx`와 `translations` 폴더를 Unity Underground 게임 폴더에 그대로 붙여넣습니다.
4. 같은 이름의 파일을 덮어쓴 뒤 게임을 실행합니다.

별도의 설치 프로그램이나 PowerShell 실행은 필요하지 않습니다. 저장소를 직접 내려받았다면 저장소 루트의 `BepInEx`와 `translations` 폴더를 동일하게 복사하면 됩니다.

기본 한글 폰트는 Windows의 `Malgun Gothic`을 사용합니다. Unity IMGUI에서 일부 동적 폰트가 글자를 반복 출력하는 문제가 있어 책·상태창과 캐릭터 생성 화면도 안전한 기본 폰트를 사용합니다.

## 재번역과 검증

재번역은 Ultima Underworld 1의 원본 `STRINGS.PAK`에서 추출한 영문을 `(blockId, stringId)` 위치별로 대조해 진행했습니다.

1. 공식 영문 원문 추출
2. 기존 한국어와 위치별 대조
3. 오역·직역투·말투와 용어 전면 검토
4. 토큰, 제어 코드, 줄바꿈과 공백 검증
5. 검토 제안 7,092개를 블록별 JSON과 전역 번역 맵에 반영
6. 124개 번역 JSON과 배포 ZIP 무결성 검사

`tools/apply_completed_retranslations.py`는 완료된 재번역 묶음을 실제 패치 데이터에 재현 가능하게 반영합니다. 같은 영문이 여러 화자에게 반복되는 경우 블록별 결과는 그대로 보존하고, 전역 번역 맵에는 가장 널리 사용된 번역을 적용합니다.

## AI 번역 파이프라인

초기 번역 파이프라인은 Gemma와 Gemini를 활용했으며, v1.1.0 전체 재번역에서는 공식 영문 대조와 위치별 수동 검토를 거쳤습니다.

`tools/google_ai_studio_key.example.txt`를 `tools/google_ai_studio_key.txt`로 복사하고 API 키와 `GAME_DIR`을 입력하면 기존 번역 도구를 사용할 수 있습니다. 실제 API 키 파일과 생성 결과는 Git에서 제외됩니다.

## 주의 사항

- 세이브 파일과 게임 원본 데이터는 수정하지 않습니다.
- 번역 적용 전 게임을 종료하는 것을 권장합니다.
- 플러그인 코드는 v1.0.1 이후 변경되지 않아 v1.1.0 패키지에서도 기존 검증 DLL을 사용합니다.
- 이 프로젝트는 Origin Systems, Electronic Arts 및 Unity Underground 제작진과 관련 없는 팬 프로젝트입니다.
