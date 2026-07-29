# Unity Underground 한국어 번역

Ultima Underworld의 Unity 포팅 프로젝트인 **Unity Underground**용 비공식 한국어 번역입니다.

게임 원본이나 Unity Underground 실행 파일은 포함하지 않습니다. 정상적으로 설치된 Unity Underground가 필요합니다.

## 포함 내용

- 시스템 메시지, 캐릭터 생성, 아이템, 주문, NPC 대화 한국어 번역
- 동적으로 조합되는 `You see ...`, 장비 파괴 메시지, 상태창 문장 처리
- 한글 출력을 위한 BepInEx 플러그인
- Gemma 4 31B 문체 분석 및 Gemini 3.5 Flash-Lite 번역 파이프라인

## 설치

1. BepInEx 5.4.23.5를 Unity Underground에 설치합니다.
2. [Releases](https://github.com/munument1/Unity-Underground-Korean/releases)에서 최신 ZIP을 받습니다.
3. ZIP 안의 `BepInEx`와 `translations` 폴더를 Unity Underground 게임 폴더에 그대로 붙여넣습니다.
4. 같은 이름의 파일을 덮어쓴 뒤 게임을 실행합니다.

별도의 설치 프로그램이나 PowerShell 실행은 필요하지 않습니다. 저장소를 직접 내려받았다면 저장소 루트의 `BepInEx`와 `translations` 폴더를 동일하게 복사하면 됩니다.

기본 한글 폰트는 Windows의 `Malgun Gothic`을 사용합니다. Unity IMGUI에서 일부 동적 폰트가 글자를 반복 출력하는 문제가 있어 책·상태창과 캐릭터 생성 화면도 안전한 기본 폰트를 사용합니다.

## AI 번역 파이프라인

`tools/translate_uu.js`는 다음 순서로 동작합니다.

1. Google AI Studio의 Gemma 4 31B로 용어·고유명사·인물별 말투 분석
2. Gemini 3.5 Flash-Lite로 번역
3. ID, 플레이스홀더, 제어코드, 줄바꿈 검증
4. 검증된 결과만 적용

`tools/google_ai_studio_key.example.txt`를 `tools/google_ai_studio_key.txt`로 복사하고 API 키와 `GAME_DIR`을 입력합니다. 실제 API 키 파일과 생성 결과는 Git에서 제외됩니다.

## 주의 사항

- 세이브 파일과 게임 원본 데이터는 수정하지 않습니다.
- 번역 적용 전 게임을 종료하는 것을 권장합니다.
- 이 프로젝트는 Origin Systems, Electronic Arts 및 Unity Underground 제작진과 관련 없는 팬 프로젝트입니다.
