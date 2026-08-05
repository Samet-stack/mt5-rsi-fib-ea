[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$InstallRoot = "C:\Program Files\MetaTrader 5"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

function Normalize-PathForComparison {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
}

$metaEditor = Join-Path $InstallRoot "metaeditor64.exe"
$sourceExpert = Join-Path $ProjectRoot "MQL5\Experts\RSIFibRetracementEA.mq5"
$sourcePresetDirectory = Join-Path $ProjectRoot "presets"
$sourcePresets = @(Get-ChildItem -LiteralPath $sourcePresetDirectory -Filter "*.set" -File -ErrorAction Stop)

if (-not (Test-Path -LiteralPath $metaEditor -PathType Leaf)) {
    throw "MetaEditor not found: $metaEditor"
}
if (-not (Test-Path -LiteralPath $sourceExpert -PathType Leaf)) {
    throw "EA source not found: $sourceExpert"
}
if ($sourcePresets.Count -eq 0) {
    throw "No tester presets found in: $sourcePresetDirectory"
}

$terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$expectedOrigin = Normalize-PathForComparison -Path $InstallRoot
$dataDirectory = $null

foreach ($candidate in Get-ChildItem -LiteralPath $terminalRoot -Directory -ErrorAction Stop) {
    $originFile = Join-Path $candidate.FullName "origin.txt"
    if (-not (Test-Path -LiteralPath $originFile -PathType Leaf)) {
        continue
    }

    $candidateOrigin = (Get-Content -LiteralPath $originFile -Raw).Trim()
    if ($candidateOrigin -and
        (Normalize-PathForComparison -Path $candidateOrigin) -ieq $expectedOrigin) {
        $dataDirectory = $candidate.FullName
        break
    }
}

if (-not $dataDirectory) {
    throw "No MT5 data directory mapped to '$InstallRoot' was found below '$terminalRoot'."
}

$expertDirectory = Join-Path $dataDirectory "MQL5\Experts\RSIFibEA"
$testerProfileDirectory = Join-Path $dataDirectory "MQL5\Profiles\Tester"
New-Item -ItemType Directory -Path $expertDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $testerProfileDirectory -Force | Out-Null

$deployedSource = Join-Path $expertDirectory "RSIFibRetracementEA.mq5"
Copy-Item -LiteralPath $sourceExpert -Destination $deployedSource -Force
foreach ($preset in $sourcePresets) {
    Copy-Item -LiteralPath $preset.FullName -Destination $testerProfileDirectory -Force
}

$compileLog = [System.IO.Path]::ChangeExtension($deployedSource, ".log")
$compiledExpert = [System.IO.Path]::ChangeExtension($deployedSource, ".ex5")
$previousLogWriteUtc = [datetime]::MinValue
if (Test-Path -LiteralPath $compileLog -PathType Leaf) {
    $previousLogWriteUtc = (Get-Item -LiteralPath $compileLog).LastWriteTimeUtc
}

$compileArgument = '/compile:"{0}"' -f $deployedSource
$process = Start-Process -FilePath $metaEditor `
                         -ArgumentList @($compileArgument, "/log") `
                         -PassThru -Wait

if (-not (Test-Path -LiteralPath $compileLog -PathType Leaf)) {
    throw "MetaEditor did not create the expected compile log: $compileLog"
}
if ((Get-Item -LiteralPath $compileLog).LastWriteTimeUtc -le $previousLogWriteUtc) {
    throw "MetaEditor did not refresh the compile log: $compileLog"
}

$compileText = Get-Content -LiteralPath $compileLog -Encoding Unicode -Raw
$resultLine = ($compileText -split "`r?`n" | Where-Object { $_ -match "Result:" } | Select-Object -Last 1)
if ($resultLine -notmatch "Result:\s+0 errors,\s+0 warnings") {
    throw "Native MQL5 compilation failed. Last result: $resultLine"
}
if (-not (Test-Path -LiteralPath $compiledExpert -PathType Leaf)) {
    throw "Compilation reported success but EX5 is missing: $compiledExpert"
}

[pscustomobject]@{
    DataDirectory = $dataDirectory
    SourceSHA256 = (Get-FileHash -LiteralPath $sourceExpert -Algorithm SHA256).Hash
    DeployedSHA256 = (Get-FileHash -LiteralPath $deployedSource -Algorithm SHA256).Hash
    CompiledExpert = $compiledExpert
    CompiledBytes = (Get-Item -LiteralPath $compiledExpert).Length
    CompileResult = $resultLine.Trim()
}
