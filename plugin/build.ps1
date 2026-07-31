param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir
)

$ErrorActionPreference = 'Stop'
$game = (Resolve-Path -LiteralPath $GameDir).Path
$managed = Join-Path $game 'UnityUnderground_Data\Managed'
$bepInEx = Join-Path $game 'BepInEx\core'
$source = Join-Path $PSScriptRoot 'UnityUndergroundKorean.cs'
$outputDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'BepInEx\plugins'
$output = Join-Path $outputDir 'UnityUndergroundKorean.dll'
$dotnet = (Get-Command dotnet -ErrorAction Stop).Source
$sdkVersion = (& $dotnet --version).Trim()
$dotnetRoot = Split-Path -Parent $dotnet
$compiler = Join-Path $dotnetRoot "sdk\$sdkVersion\Roslyn\bincore\csc.dll"

if (-not (Test-Path -LiteralPath $compiler)) {
    throw "C# 컴파일러를 찾을 수 없습니다: $compiler"
}

$references = @(
    "$managed\mscorlib.dll",
    "$managed\System.dll",
    "$managed\System.Core.dll",
    "$managed\System.Runtime.dll",
    "$managed\netstandard.dll",
    "$bepInEx\BepInEx.dll",
    "$bepInEx\0Harmony.dll",
    "$managed\Newtonsoft.Json.dll",
    "$managed\UnityEngine.dll",
    "$managed\UnityEngine.CoreModule.dll",
    "$managed\UnityEngine.UI.dll",
    "$managed\Unity.TextMeshPro.dll",
    "$managed\UnityEngine.TextRenderingModule.dll",
    "$managed\UnityEngine.IMGUIModule.dll"
)

foreach ($reference in $references) {
    if (-not (Test-Path -LiteralPath $reference)) {
        throw "필수 참조 파일이 없습니다: $reference"
    }
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$arguments = @(
    $compiler,
    '/nologo',
    '/noconfig',
    '/nostdlib+',
    '/target:library',
    '/platform:anycpu',
    '/langversion:7.3',
    '/optimize+',
    '/deterministic+',
    '/debug-',
    "/out:$output"
) + ($references | ForEach-Object { "/reference:$_" }) + $source

& $dotnet @arguments
if ($LASTEXITCODE -ne 0) {
    throw "빌드 실패: 종료 코드 $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $output) -or (Get-Item -LiteralPath $output).Length -eq 0) {
    throw "빌드 결과 DLL이 생성되지 않았습니다: $output"
}

Write-Host "빌드 완료: $output"
Write-Host "DLL 크기: $((Get-Item -LiteralPath $output).Length) bytes"
