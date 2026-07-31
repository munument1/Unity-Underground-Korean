#!/usr/bin/env bash
set -euo pipefail

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

curl --fail --location --retry 3 \
  https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip \
  --output "$work_dir/bepinex.zip"
unzip -q "$work_dir/bepinex.zip" -d "$work_dir/bepinex"

bepinex_dll="$work_dir/bepinex/BepInEx/core/BepInEx.dll"
harmony_dll="$work_dir/bepinex/BepInEx/core/0Harmony.dll"
test -f "$bepinex_dll"
test -f "$harmony_dll"

cat > plugin/UnityUndergroundKorean.csproj <<EOF
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.0</TargetFramework>
    <LangVersion>7.3</LangVersion>
    <AssemblyName>UnityUndergroundKorean</AssemblyName>
    <RootNamespace>UnityUndergroundKorean</RootNamespace>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
    <OutputPath>../BepInEx/plugins/</OutputPath>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="UnityUndergroundKorean.cs" />
    <Reference Include="BepInEx">
      <HintPath>$bepinex_dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="0Harmony">
      <HintPath>$harmony_dll</HintPath>
      <Private>false</Private>
    </Reference>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.2" PrivateAssets="all" />
    <PackageReference Include="UnityEngine.Modules" Version="2021.3.33" PrivateAssets="all" />
  </ItemGroup>
</Project>
EOF

dotnet build plugin/UnityUndergroundKorean.csproj -c Release
test -f BepInEx/plugins/UnityUndergroundKorean.dll
rm -f plugin/UnityUndergroundKorean.csproj
