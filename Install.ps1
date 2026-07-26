param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$game = (Resolve-Path -LiteralPath $GameDir).Path
$pluginDir = Join-Path $game 'BepInEx\plugins'
$translationDir = Join-Path $game 'translations'

if (-not (Test-Path -LiteralPath (Join-Path $game 'UnityUnderground.exe'))) {
    throw "UnityUnderground.exe를 찾을 수 없습니다: $game"
}
if (-not (Test-Path -LiteralPath (Join-Path $game 'BepInEx'))) {
    throw "BepInEx가 설치되어 있지 않습니다: $game"
}
if (Get-Process -Name 'UnityUnderground' -ErrorAction SilentlyContinue) {
    throw '게임을 완전히 종료한 뒤 다시 실행하세요.'
}

New-Item -ItemType Directory -Force -Path $pluginDir, $translationDir | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'plugin\UnityUndergroundKorean.dll') -Destination $pluginDir -Force
Copy-Item -Path (Join-Path $root 'translations\*.json') -Destination $translationDir -Force

Write-Host "설치 완료: $game"
