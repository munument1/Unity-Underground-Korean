#!/usr/bin/env bash
set -euo pipefail

DLL='BepInEx/plugins/UnityUndergroundKorean.dll'
ARCHIVE='dist/Unity-Underground-Korean-v1.1.0.zip'
CHECKSUM='dist/Unity-Underground-Korean-v1.1.0.zip.sha256'
DLL_SHA='eabccfe2ebe21e2b882ca22c45177291d69db88b063df3fcad5a50c3e008eb20'
ZIP_SHA='7ab034e4072dd466bcbda65d5ed4d1116ec8e318ae6fff619b8c3ad37e9c71cd'

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

report = json.loads(Path('retranslation/APPLY_REPORT.json').read_text(encoding='utf-8'))
assert report['reviewedLocationCount'] == 7092
assert report['dynamicSkipCount'] == 48
assert report['unresolvedCount'] == 0
assert report['validationIssueCount'] == 0

translations = sorted(Path('translations').glob('*.json'))
assert len(translations) == 124
for path in translations:
    json.loads(path.read_text(encoding='utf-8'))

source = Path('plugin/UnityUndergroundKorean.cs').read_text(encoding='utf-8')
assert '[BepInPlugin("kr.ultima-underworld.korean", "Unity Underground Korean", "1.1.0")]' in source
assert 'return "시도했지만 " + item + "에는 아무런 효과가 없습니다.";' in source
assert 'TryTranslateObjectPrefix(value, "Your attempt has no effect on the "' not in source

build = Path('plugin/build.ps1').read_text(encoding='utf-8')
assert "'/nostdlib+'" in build
assert 'AssemblyVersion("1.1.0.0")' in build
assert 'Exiled.Dev.References' not in build

dll = Path('BepInEx/plugins/UnityUndergroundKorean.dll')
assert dll.stat().st_size == 24576
assert hashlib.sha256(dll.read_bytes()).hexdigest() == 'eabccfe2ebe21e2b882ca22c45177291d69db88b063df3fcad5a50c3e008eb20'

dist = Path('dist')
dist.mkdir(exist_ok=True)
archive = dist / 'Unity-Underground-Korean-v1.1.0.zip'
checksum = dist / 'Unity-Underground-Korean-v1.1.0.zip.sha256'
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

archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive.stat().st_size == 456460
assert archive_hash == '7ab034e4072dd466bcbda65d5ed4d1116ec8e318ae6fff619b8c3ad37e9c71cd'
checksum.write_text(f'{archive_hash}  {archive.name}\n', encoding='ascii')
PY

git diff --check

rm -f retranslation/.final_dll.b64.*
rm -f retranslation/RUNTIME_BUILD_LOG.txt
rm -f tools/finalize_v1_1_runtime.py
rm -f tools/finalize_release_v1_1_0.sh
rm -f .github/workflows/apply-actual-dll-v1.1.0.yml
rm -f .github/workflows/export-v1.1.0-build-kit.yml
rm -f .github/workflows/fix-no-effect-v1.1.0.yml
rm -f .github/workflows/validate-v1.1.0-release.yml
rm -f .github/workflows/release-v1.1.0.yml
rm -f .github/workflows/finalize-runtime-v1.1.0.yml

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -A
git reset -- dist || true
git commit -m 'v1.1.0 실제 게임 참조 DLL 최종 확정'
git push origin HEAD:main

final_sha="$(git rev-parse HEAD)"
git tag -f v1.1.0 "$final_sha"
git push origin refs/tags/v1.1.0 --force

if gh release view v1.1.0 >/dev/null 2>&1; then
    gh release upload v1.1.0 "$ARCHIVE" "$CHECKSUM" --clobber
    gh release edit v1.1.0 \
        --title 'Unity Underground 한국어 완전 재번역 v1.1.0' \
        --notes-file RELEASE_NOTES_v1.1.0.md \
        --draft=false \
        --prerelease=false \
        --latest
else
    gh release create v1.1.0 "$ARCHIVE" "$CHECKSUM" \
        --target "$final_sha" \
        --title 'Unity Underground 한국어 완전 재번역 v1.1.0' \
        --notes-file RELEASE_NOTES_v1.1.0.md \
        --latest
fi
