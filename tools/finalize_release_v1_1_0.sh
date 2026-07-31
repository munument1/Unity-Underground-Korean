#!/usr/bin/env bash
set -euo pipefail

DLL='BepInEx/plugins/UnityUndergroundKorean.dll'
ARCHIVE='dist/Unity-Underground-Korean-v1.1.0.zip'
CHECKSUM='dist/Unity-Underground-Korean-v1.1.0.zip.sha256'
DLL_SHA='eabccfe2ebe21e2b882ca22c45177291d69db88b063df3fcad5a50c3e008eb20'

mkdir -p "$(dirname "$DLL")" dist
cat retranslation/.final_dll.b64.* | base64 --decode > "$DLL"
test "$(stat -c %s "$DLL")" = '24576'
echo "$DLL_SHA  $DLL" | sha256sum --check

python - <<'PY'
from pathlib import Path

path = Path('plugin/UnityUndergroundKorean.cs')
text = path.read_text(encoding='utf-8')
old = '''            if (TryTranslateObjectPrefix(value, "Your attempt has no effect on the ", "에는 아무런 효과가 없습니다.", out fragment))
                return "시도했지만 " + fragment;
'''
new = '''            if (TryTakePrefix(value, "Your attempt has no effect on the ", out fragment))
            {
                string item = StripLeadingEnglishArticle(
                    TranslateKnownFragment(fragment)).TrimEnd('.');
                if (ContainsKorean(item))
                    return "시도했지만 " + item + "에는 아무런 효과가 없습니다.";
            }
'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('no-effect sentence pattern not found')
path.write_text(text, encoding='utf-8')
PY

python - <<'PY'
import hashlib
import json
import zipfile
from pathlib import Path

translations = sorted(Path('translations').glob('*.json'))
assert len(translations) == 124, len(translations)
for path in translations:
    json.loads(path.read_text(encoding='utf-8'))

source = Path('plugin/UnityUndergroundKorean.cs').read_text(encoding='utf-8')
assert '[BepInPlugin("kr.ultima-underworld.korean", "Unity Underground Korean", "1.1.0")]' in source
assert 'return "시도했지만 " + item + "에는 아무런 효과가 없습니다.";' in source

build = Path('plugin/build.ps1').read_text(encoding='utf-8')
assert "'/nostdlib+'" in build
assert 'AssemblyVersion("1.1.0.0")' in build
assert 'Exiled.Dev.References' not in build

dll = Path('BepInEx/plugins/UnityUndergroundKorean.dll')
assert dll.stat().st_size == 24576
assert hashlib.sha256(dll.read_bytes()).hexdigest() == 'eabccfe2ebe21e2b882ca22c45177291d69db88b063df3fcad5a50c3e008eb20'

archive = Path('dist/Unity-Underground-Korean-v1.1.0.zip')
checksum = Path('dist/Unity-Underground-Korean-v1.1.0.zip.sha256')
fixed_time = (2026, 7, 31, 0, 0, 0)
files = [(dll, 'BepInEx/plugins/UnityUndergroundKorean.dll')]
files.extend((path, 'translations/' + path.name) for path in translations)
assert len(files) == 125

with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for source_path, target in files:
        info = zipfile.ZipInfo(target, fixed_time)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        zf.writestr(info, source_path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

with zipfile.ZipFile(archive) as zf:
    names = zf.namelist()
    assert len(names) == 125
    assert len(set(names)) == 125
    assert zf.testzip() is None
    assert hashlib.sha256(zf.read('BepInEx/plugins/UnityUndergroundKorean.dll')).hexdigest() == 'eabccfe2ebe21e2b882ca22c45177291d69db88b063df3fcad5a50c3e008eb20'

archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
checksum.write_text(f'{archive_hash}  {archive.name}\n', encoding='ascii')
print(f'archive_size={archive.stat().st_size}')
print(f'archive_sha256={archive_hash}')
PY

git diff --check

# 저장소에는 최종 DLL과 소스 수정만 반영한다. 워크플로 파일 정리는 성공 확인 후 별도로 처리한다.
rm -f retranslation/.final_dll.b64.*
rm -f retranslation/RUNTIME_BUILD_LOG.txt
rm -f tools/finalize_v1_1_runtime.py

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add "$DLL" plugin/UnityUndergroundKorean.cs retranslation tools/finalize_v1_1_runtime.py 2>/dev/null || true
git reset -- dist tools/finalize_release_v1_1_0.sh || true
if ! git diff --cached --quiet; then
    git commit -m 'v1.1.0 실제 게임 참조 DLL 최종 확정'
    git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git push origin HEAD:main
fi

final_sha="$(git rev-parse HEAD)"
git tag -f v1.1.0 "$final_sha"
git push origin refs/tags/v1.1.0 --force

if gh release view v1.1.0 >/dev/null 2>&1; then
    gh release upload v1.1.0 "$ARCHIVE" "$CHECKSUM" --clobber
else
    gh release create v1.1.0 "$ARCHIVE" "$CHECKSUM" \
        --target "$final_sha" \
        --title 'Unity Underground 한국어 완전 재번역 v1.1.0' \
        --notes-file RELEASE_NOTES_v1.1.0.md
fi
