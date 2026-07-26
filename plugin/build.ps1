param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir
)

$ErrorActionPreference = 'Stop'
$game = (Resolve-Path -LiteralPath $GameDir).Path
$managed = Join-Path $game 'UnityUnderground_Data\Managed'
$bepInEx = Join-Path $game 'BepInEx\core'
$source = Join-Path $PSScriptRoot 'UnityUndergroundKorean.cs'
$output = Join-Path $PSScriptRoot 'UnityUndergroundKorean.dll'
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

$arguments = @(
    $compiler,
    '/nologo',
    '/target:library',
    '/langversion:7.3',
    "/out:$output"
) + ($references | ForEach-Object { "/reference:$_" }) + $source

& $dotnet @arguments
if ($LASTEXITCODE -ne 0) {
    throw "빌드 실패: 종료 코드 $LASTEXITCODE"
}

Write-Host "빌드 완료: $output"
