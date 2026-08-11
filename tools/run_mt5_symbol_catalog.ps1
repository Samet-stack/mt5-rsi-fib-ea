[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$BootstrapSymbol = "EURUSD",
    [string]$ProjectRoot = "",
    [string]$InstallRoot = "C:\Program Files\MetaTrader 5",
    [ValidateRange(30, 900)]
    [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$terminal = Join-Path $InstallRoot "terminal64.exe"
$metaEditor = Join-Path $InstallRoot "metaeditor64.exe"
$source = Join-Path $ProjectRoot "MQL5\Experts\RSIFibSymbolCatalogEA.mq5"
foreach ($required in @($terminal, $metaEditor, $source)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file missing: $required"
    }
}

$terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$expectedOrigin = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$dataDirectory = $null
foreach ($candidate in Get-ChildItem -LiteralPath $terminalRoot -Directory) {
    $originFile = Join-Path $candidate.FullName "origin.txt"
    if (-not (Test-Path -LiteralPath $originFile -PathType Leaf)) { continue }
    $candidateOrigin = (Get-Content -LiteralPath $originFile -Raw).Trim()
    if ($candidateOrigin -and
        [IO.Path]::GetFullPath($candidateOrigin).TrimEnd('\') -ieq $expectedOrigin) {
        $dataDirectory = $candidate.FullName
        break
    }
}
if (-not $dataDirectory) {
    throw "No MT5 data directory mapped to '$InstallRoot' was found."
}
if (@(Get-Process -Name "terminal64" -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "MT5 is already running. Close it before the isolated symbol catalog."
}

$expertDirectory = Join-Path $dataDirectory "MQL5\Experts\RSIFibEA"
New-Item -ItemType Directory -Path $expertDirectory -Force | Out-Null
$deployedSource = Join-Path $expertDirectory "RSIFibSymbolCatalogEA.mq5"
Copy-Item -LiteralPath $source -Destination $deployedSource -Force
$compileLog = [IO.Path]::ChangeExtension($deployedSource, ".log")
$compiledExpert = [IO.Path]::ChangeExtension($deployedSource, ".ex5")
$previousCompileUtc = [datetime]::MinValue
if (Test-Path -LiteralPath $compileLog -PathType Leaf) {
    $previousCompileUtc = (Get-Item -LiteralPath $compileLog).LastWriteTimeUtc
}
$compileArgument = '/compile:"{0}"' -f $deployedSource
Start-Process -FilePath $metaEditor -ArgumentList @($compileArgument, "/log") -Wait
if (-not (Test-Path -LiteralPath $compileLog -PathType Leaf) -or
    (Get-Item -LiteralPath $compileLog).LastWriteTimeUtc -le $previousCompileUtc) {
    throw "MetaEditor did not refresh the catalog compile log."
}
$compileText = Get-Content -LiteralPath $compileLog -Encoding Unicode -Raw
$compileResult = ($compileText -split "`r?`n" |
    Where-Object { $_ -match "Result:" } | Select-Object -Last 1)
if ($compileResult -notmatch "Result:\s+0 errors,\s+0 warnings" -or
    -not (Test-Path -LiteralPath $compiledExpert -PathType Leaf)) {
    throw "Symbol catalog compilation failed: $compileResult"
}

$commonFiles = Join-Path $terminalRoot "Common\Files\RSIFibEA"
New-Item -ItemType Directory -Path $commonFiles -Force | Out-Null
$catalogPath = Join-Path $commonFiles "symbol_catalog.csv"
$previousCatalogUtc = [datetime]::MinValue
if (Test-Path -LiteralPath $catalogPath -PathType Leaf) {
    $previousCatalogUtc = (Get-Item -LiteralPath $catalogPath).LastWriteTimeUtc
}

$runtimeDirectory = Join-Path $env:LOCALAPPDATA "RSIFibEA"
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$configPath = Join-Path $runtimeDirectory "symbol_catalog.ini"
$configuration = @"
; Tester-only read-only symbol catalog. Contains no account credentials.
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0

[Tester]
Expert=RSIFibEA\RSIFibSymbolCatalogEA
Symbol=$BootstrapSymbol
Period=M1
Deposit=3000.00
Currency=USD
Leverage=1:100
Model=1
ExecutionMode=0
Optimization=0
FromDate=2026.07.01
ToDate=2026.07.02
ForwardMode=0
Report=RSIFibEA_symbol_catalog
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@
[IO.File]::WriteAllText($configPath, $configuration,
    (New-Object Text.UTF8Encoding($false)))

$process = Start-Process -FilePath $terminal `
                         -ArgumentList ("/config:" + $configPath) `
                         -PassThru
$deadline = [datetime]::UtcNow.AddSeconds($TimeoutSeconds)
$rows = $null
do {
    Start-Sleep -Milliseconds 250
    if (Test-Path -LiteralPath $catalogPath -PathType Leaf) {
        $catalogItem = Get-Item -LiteralPath $catalogPath
        if ($catalogItem.LastWriteTimeUtc -gt $previousCatalogUtc) {
            try {
                $rows = @(Import-Csv -LiteralPath $catalogPath -Delimiter ';' -ErrorAction Stop)
            }
            catch [System.IO.IOException] {
                $rows = $null
            }
        }
    }
} while ($null -eq $rows -and [datetime]::UtcNow -lt $deadline)

if ($null -eq $rows) {
    throw "MT5 did not create a readable fresh symbol catalog before timeout: $catalogPath"
}
foreach ($row in $rows) {
    if ($row.schema -ne "rsifib-mt5-symbol-catalog/v1" -or
        $row.tester_only -ne "true" -or [int]$row.orders_sent -ne 0) {
        throw "The symbol catalog failed its safety/schema validation."
    }
}

do {
    Start-Sleep -Milliseconds 250
    $terminalProcesses = @(Get-Process -Name "terminal64" -ErrorAction SilentlyContinue)
} while ($terminalProcesses.Count -gt 0 -and [datetime]::UtcNow -lt $deadline)
if ($terminalProcesses.Count -gt 0) {
    throw "MT5 produced the catalog but did not shut down before timeout; no forced termination was attempted."
}

$rows | Select-Object symbol, description, path, trade_mode, calc_mode,
    tick_size, tick_value, contract_size, volume_min, volume_step,
    start_time, expiration_time
