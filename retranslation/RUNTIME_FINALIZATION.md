# v1.1.0 런타임 최종 검증

- 플러그인 어셈블리: `UnityUndergroundKorean|1.1.0.0||0`
- 기존 DLL: 20480 bytes, `b60694b466f97df71f070c02005516ee49ee3bf584a93eba9ff47cfe888797f1`
- 새 DLL: 25088 bytes, `6e327015d35b14f3f68a603529e09795fe9fcc399b34ec68dc2271e6956a1c64`
- 번역 JSON: 124개
- 배포 파일: 125개
- 후보 ZIP: 456864 bytes, `1793b998ef25104ed651ec4d11cc05bb53ebaa4df0ba113f1998964586922da4`
- 미해결 원문 대응: 0개
- 구조 검증 오류: 0개
- 실제 게임 참조 DLL은 Google Drive에 비공개 보관하며 GitHub에는 커밋하지 않음
- 로컬 `plugin/build.ps1`은 실제 게임 DLL을 `/nostdlib+`로 직접 참조
- CI는 런타임 어셈블리 정체성과 일치하는 Unity UI 컴파일 스텁만 임시 생성
