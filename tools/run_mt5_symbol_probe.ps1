[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Symbol = "XAUUSD",

    [ValidatePattern('^\d{4}\.\d{2}\.\d{2}$')]
    [string]$FromDate = "2026.07.01",

    [ValidatePattern('^\d{4}\.\d{2}\.\d{2}$')]
    [string]$ToDate = "2026.07.02",

    [ValidateRange(1.0, 1000000000.0)]
    [double]$Deposit = 3000.0,

    [ValidateRange(1, 5000)]
    [int]$Leverage = 100,

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

$from = [datetime]::ParseExact($FromDate, "yyyy.MM.dd", [Globalization.CultureInfo]::InvariantCulture)
$to = [datetime]::ParseExact($ToDate, "yyyy.MM.dd", [Globalization.CultureInfo]::InvariantCulture)
if ($to -le $from) {
    throw "ToDate must be later than FromDate."
}

$terminal = Join-Path $InstallRoot "terminal64.exe"
$metaEditor = Join-Path $InstallRoot "metaeditor64.exe"
$source = Join-Path $ProjectRoot "MQL5\Experts\RSIFibSymbolProbeEA.mq5"
foreach ($required in @($terminal, $metaEditor, $source)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file missing: $required"
    }
}

$terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$expectedOrigin = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$dataDirectory = $null
foreach ($candidate in Get-ChildItem -LiteralPath $terminalRoot -Directory -ErrorAction Stop) {
    $originFile = Join-Path $candidate.FullName "origin.txt"
    if (-not (Test-Path -LiteralPath $originFile -PathType Leaf)) {
        continue
    }
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

$running = @(Get-Process -Name "terminal64" -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    throw "MT5 is already running. Close it before the isolated symbol probe."
}

$expertDirectory = Join-Path $dataDirectory "MQL5\Experts\RSIFibEA"
New-Item -ItemType Directory -Path $expertDirectory -Force | Out-Null
$deployedSource = Join-Path $expertDirectory "RSIFibSymbolProbeEA.mq5"
Copy-Item -LiteralPath $source -Destination $deployedSource -Force

$compileLog = [IO.Path]::ChangeExtension($deployedSource, ".log")
$compiledExpert = [IO.Path]::ChangeExtension($deployedSource, ".ex5")
$previousCompileUtc = [datetime]::MinValue
if (Test-Path -LiteralPath $compileLog -PathType Leaf) {
    $previousCompileUtc = (Get-Item -LiteralPath $compileLog).LastWriteTimeUtc
}
$compileArgument = '/compile:"{0}"' -f $deployedSource
$compileProcess = Start-Process -FilePath $metaEditor `
                                -ArgumentList @($compileArgument, "/log") `
                                -PassThru -Wait
if (-not (Test-Path -LiteralPath $compileLog -PathType Leaf) -or
    (Get-Item -LiteralPath $compileLog).LastWriteTimeUtc -le $previousCompileUtc) {
    throw "MetaEditor did not refresh the probe compile log."
}
$compileText = Get-Content -LiteralPath $compileLog -Encoding Unicode -Raw
$compileResult = ($compileText -split "`r?`n" | Where-Object { $_ -match "Result:" } | Select-Object -Last 1)
if ($compileResult -notmatch "Result:\s+0 errors,\s+0 warnings" -or
    -not (Test-Path -LiteralPath $compiledExpert -PathType Leaf)) {
    throw "Symbol probe compilation failed: $compileResult"
}

$commonFiles = Join-Path $terminalRoot "Common\Files\RSIFibEA"
New-Item -ItemType Directory -Path $commonFiles -Force | Out-Null
$probePath = Join-Path $commonFiles "symbol_probe.json"
$previousProbeUtc = [datetime]::MinValue
if (Test-Path -LiteralPath $probePath -PathType Leaf) {
    $previousProbeUtc = (Get-Item -LiteralPath $probePath).LastWriteTimeUtc
}

$runtimeDirectory = Join-Path $env:LOCALAPPDATA "RSIFibEA"
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$configPath = Join-Path $runtimeDirectory "symbol_probe.ini"
$reportName = "RSIFibEA_symbol_probe_{0}" -f $Symbol
$depositText = $Deposit.ToString("0.00", [Globalization.CultureInfo]::InvariantCulture)
$configuration = @"
; Read-only symbol probe. Contains no account credentials.
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0

[Tester]
Expert=RSIFibEA\RSIFibSymbolProbeEA
Symbol=$Symbol
Period=M1
Deposit=$depositText
Currency=USD
Leverage=1:$Leverage
Model=4
ExecutionMode=0
Optimization=0
FromDate=$FromDate
ToDate=$ToDate
ForwardMode=0
Report=$reportName
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"@
[IO.File]::WriteAllText($configPath, $configuration, (New-Object Text.UTF8Encoding($false)))

$process = Start-Process -FilePath $terminal `
                         -ArgumentList ("/config:" + $configPath) `
                         -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    throw "MT5 symbol probe exceeded $TimeoutSeconds seconds; no forced termination was attempted."
}
if ($process.ExitCode -ne 0) {
    throw "MT5 symbol probe exited with code $($process.ExitCode)."
}
if (-not (Test-Path -LiteralPath $probePath -PathType Leaf) -or
    (Get-Item -LiteralPath $probePath).LastWriteTimeUtc -le $previousProbeUtc) {
    throw "MT5 did not create a fresh symbol probe: $probePath"
}

$probe = Get-Content -LiteralPath $probePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($probe.schema -ne "rsifib-mt5-symbol-probe/v1" -or
    $probe.tester_only -ne $true -or
    [int]$probe.orders_sent -ne 0 -or
    $probe.symbol -ne $Symbol) {
    throw "The symbol probe output failed its safety/schema validation."
}

[pscustomobject]@{
    Symbol = $probe.symbol
    Server = $probe.server
    ContractSize = $probe.contract_size
    TickSize = $probe.tick_size
    TickValue = $probe.tick_value
    VolumeMin = $probe.volume_min
    VolumeStep = $probe.volume_step
    MinVolumeMarginBuy = $probe.min_volume_margin_buy
    MinVolumeOneTickLossBuy = $probe.min_volume_one_tick_buy_pnl
    OrdersSent = $probe.orders_sent
    Probe = $probePath
    CompileResult = $compileResult.Trim()
}
