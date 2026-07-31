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
$assemblyInfo = Join-Path $PSScriptRoot '.UnityUndergroundKorean.AssemblyInfo.cs'
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
@'
using System.Reflection;
[assembly: AssemblyVersion("1.1.0.0")]
[assembly: AssemblyFileVersion("1.1.0.0")]
[assembly: AssemblyInformationalVersion("1.1.0")]
'@ | Set-Content -LiteralPath $assemblyInfo -Encoding UTF8

try {
    $arguments = @(
        $compiler,
        '/nologo',
        '/target:library',
        '/langversion:7.3',
        '/nostdlib+',
        '/deterministic+',
        '/optimize+',
        '/debug-',
        "/out:$output"
    ) + ($references | ForEach-Object { "/reference:$_" }) + @(
        $assemblyInfo,
        $source
    )

    & $dotnet @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "빌드 실패: 종료 코드 $LASTEXITCODE"
    }
}
finally {
    Remove-Item -LiteralPath $assemblyInfo -Force -ErrorAction SilentlyContinue
}

$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "빌드 완료: $output"
Write-Host "크기: $((Get-Item -LiteralPath $output).Length) bytes"
Write-Host "SHA-256: $hash"
