#!/usr/bin/env python3
"""
Automated Strategy Optimization & Training Engine for RSIFibEA on MT5.
Executes systematic backtests across parameter spaces and multi-month windows.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.parse_mt5_report import parse_report

MT5_TERMINAL = Path(os.environ.get(
    "RSIFIB_MT5_TERMINAL",
    "/mnt/c/Program Files/MetaTrader 5/terminal64.exe",
))


def _required_directory(variable: str, *, create: bool = False) -> Path:
    """Return a user-supplied MT5 path without embedding local account data."""
    value = os.environ.get(variable, "").strip()
    if not value:
        raise RuntimeError(
            f"{variable} is required; see CONTRIBUTING.md for the local MT5 setup"
        )
    path = Path(value).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise RuntimeError(f"{variable} is not a directory: {path}")
    return path


def _windows_path(path: Path) -> str:
    """Convert a WSL path for the Windows terminal /config argument."""
    result = subprocess.run(
        ["wslpath", "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    converted = result.stdout.strip()
    if not converted:
        raise RuntimeError(f"wslpath returned an empty path for {path}")
    return converted

BASE_TEMPLATE = {
    "InpTradeDirection": "0",
    "InpDemoOnly": "true",
    "InpMagicNumber": "20260806",
    "InpRiskPercent": "0.10",
    "InpMaxDailyLossPct": "5.0",
    "InpMaxDailyTrades": "5",
    "InpMaxConsecutiveLosses": "3",
    "InpPortfolioMagicMin": "0",
    "InpPortfolioMagicMax": "0",
    "InpMaxPortfolioActiveExposures": "0",
    "InpMaxPortfolioDailyTrades": "0",
    "InpMaxPortfolioDailyLossPct": "0.0",
    "InpMaxSpreadPoints": "0",
    "InpMaxSpreadRiskPct": "25.0",
    "InpCloseUnprotectedPosition": "true",
    "InpStateWatchdogMs": "1000",
    "InpCostModelVerified": "false",
    "InpEstimatedRoundTurnCostPerLot": "0.0",
    "InpAdverseEntrySlippageTicks": "1",
    "InpAdverseStopSlippageTicks": "1",
    "InpMaxFreeMarginUsagePct": "25.0",
    "InpMinDaysToContractExpiry": "7",
    "InpUseSessionFilter": "true",
    "InpStartHour": "7",
    "InpEndHour": "19",
    "InpRSI_Period": "14",
    "InpRSI_AppliedPrice": "0",
    "InpSignalTimeframe": "15",
    "InpOversoldLevel": "30.0",
    "InpOverboughtLevel": "70.0",
    "InpUseRSIQualityFilter": "false",
    "InpRSIMinBarsInZone": "2",
    "InpRSIMinExitDelta": "4.0",
    "InpUseRSIDivergence": "false",
    "InpRSIDivLookbackBars": "15",
    "InpRSIDivMinPivotDiff": "2.0",
    "InpRequireRSIDivergence": "false",
    # MT5 .set files require numeric enum values and unquoted strings.
    "InpNewsMode": "0",
    "InpTesterNewsFile": r"RSIFibEA\news_events_v1.csv",
    "InpNewsMinsBefore": "30",
    "InpNewsMinsAfter": "30",
    "InpNewsCurrency": "USD",
    "InpNewsMinImportance": "3",
    "InpUseMarketStructure": "false",
    "InpStructureSwingBars": "5",
    "InpRequireStructureBOS": "true",
    "InpUseSweepBuffer": "false",
    "InpSweepLookbackBars": "5",
    "InpSweepBufferATR": "0.3",
    "InpUseStagnationExit": "false",
    "InpStagnationMaxBars": "8",
    "InpFridayFilter": "true",
    "InpFridayMaxHour": "15",
    "InpCloseFridayEOD": "true",
    "InpFridayCloseHour": "20",
    "InpUseMTFTrendFilter": "false",
    "InpMTFTimeframe": "16385",
    "InpMTFEMAPeriod": "200",
    "InpMTFRequireEMASlope": "false",
    "InpMTFSlopeLookbackBars": "8",
    "InpMTFMinSlopePct": "0.0",
    "InpMTFUseRSIConfirm": "false",
    "InpMTFRSIPeriod": "14",
    "InpMTFRSIMidline": "50.0",
    "InpUseVolatilityRegime": "false",
    "InpVolFastATRPeriod": "14",
    "InpVolSlowATRPeriod": "100",
    "InpVolMinRatio": "0.80",
    "InpVolMaxRatio": "2.20",
    "InpMinImpulseBars": "1",
    "InpAnchorWaitBars": "8",
    "InpPendingOrderBars": "8",
    "InpMinRangeATR": "0.0",
    "InpMaxRangeATR": "0.0",
    "InpATR_Period": "14",
    "InpEntryRatio": "-0.21",
    "InpStopRatio": "-0.29",
    "InpTargetRatio": "2.56",
    "InpVisualTargetRatio": "2.64",
    "InpUseAdaptiveSL": "true",
    "InpMinSLATRMultiple": "1.8",
    "InpUseAdaptiveTP": "true",
    "InpTPRiskMultiple": "4.0",
    "InpUsePartialTP": "false",
    "InpPartialTPRiskMultiple": "2.5",
    "InpPartialClosePercent": "50.0",
    "InpPartialLockBE": "true",
    "InpUseBreakEven": "true",
    "InpBETriggerFibRatio": "0.618",
    "InpBEOffsetTicks": "2",
    "InpBreakEvenCoversCosts": "true",
    "InpUseFibTrailingStop": "true",
    "InpUseRiskTrailingStop": "false",
    "InpRiskTrailTriggerR": "1.00",
    "InpRiskTrailLockR": "0.00",
    "InpRiskTrailStepR": "0.50",
    "InpDrawChartObjects": "false",
    "InpVerboseLog": "true",
    "InpShowDashboard": "false",
    "InpDashboardInTester": "false",
    "InpTesterMinTrades": "15",
    "InpTesterTargetTrades": "60",
    "InpTesterMaxDDPct": "25.0",
    "InpTesterPFCap": "5.0",
    "InpTesterSharpeCap": "5.0",
}


def _validate_research_parameters(params: Dict[str, Any]) -> None:
    if str(params.get("InpCostModelVerified", "false")).lower() != "true":
        raise RuntimeError(
            "Backtest refused: provide a verified broker cost model explicitly "
            "instead of changing the public safe default"
        )

    risk_percent = float(params.get("InpRiskPercent", 0.0))
    if risk_percent > 0.25 and os.environ.get(
        "RSIFIB_ALLOW_HIGH_RISK_TESTER", ""
    ) != "YES":
        raise RuntimeError(
            "Risk above 0.25% is disabled by default. For tester-only legacy "
            "reproduction, set RSIFIB_ALLOW_HIGH_RISK_TESTER=YES explicitly."
        )

def generate_set_file(params: Dict[str, Any], filename: str) -> Path:
    profiles_tester_dir = _required_directory("RSIFIB_MT5_DATA_DIR") / "MQL5/Profiles/Tester"
    profiles_tester_dir.mkdir(parents=True, exist_ok=True)
    set_path = profiles_tester_dir / filename
    full_params = dict(BASE_TEMPLATE)
    full_params.update(params)
    _validate_research_parameters(full_params)
    with open(set_path, "w", encoding="utf-8") as f:
        f.write(f"; Auto-Generated Optimization Preset: {filename}\n")
        for k, v in full_params.items():
            f.write(f"{k}={v}\n")
    return set_path

def generate_ini_file(set_filename: str, report_name: str, deposit: float, from_date: str, to_date: str) -> Path:
    local_ini_dir = _required_directory("RSIFIB_MT5_CONFIG_DIR", create=True)
    ini_path = local_ini_dir / "auto_opt.ini"
    content = f"""[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0

[Tester]
Expert=RSIFibEA\\RSIFibRetracementEA
ExpertParameters={set_filename}
Symbol=XAUUSD
Period=M15
Deposit={deposit:.2f}
Currency=USD
Leverage=1:100
Model=4
ExecutionMode=0
Optimization=0
OptimizationCriterion=6
FromDate={from_date}
ToDate={to_date}
ForwardMode=0
Report={report_name}
ReplaceReport=1
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
"""
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(content)
    return ini_path

def run_single_backtest(params: Dict[str, Any], name: str, deposit: float = 2000.0, from_date: str = "2026.05.01", to_date: str = "2026.08.01") -> Dict[str, Any]:
    set_filename = f"opt_{name}.set"
    report_name = f"opt_rep_{name}"
    generate_set_file(params, set_filename)
    ini_path = generate_ini_file(set_filename, report_name, deposit, from_date, to_date)
    
    mt5_data_dir = _required_directory("RSIFIB_MT5_DATA_DIR")
    report_html = mt5_data_dir / f"{report_name}.htm"
    if report_html.exists():
        try:
            report_html.unlink()
        except Exception:
            pass

    cmd = [
        str(MT5_TERMINAL),
        f"/config:{_windows_path(ini_path)}",
    ]
    subprocess.run(cmd, check=False)

    # Wait for report generation
    max_wait = 45
    start = time.time()
    while not report_html.exists() and (time.time() - start) < max_wait:
        time.sleep(0.8)
    
    time.sleep(1.2)

    if not report_html.exists():
        return {"name": name, "error": "Report file not found", "net_profit": -9999.0}

    try:
        parsed = parse_report(report_html)
        net_profit = float(parsed.get("net_profit", 0.0))
        pf = float(parsed.get("profit_factor", 0.0))
        sharpe = float(parsed.get("sharpe", 0.0))
        trades = int(parsed.get("trades", 0))
        win_trades = int(parsed.get("winners", 0))
        drawdown_pct = float(parsed.get("equity_drawdown_max_pct", 0.0))
        payoff = float(parsed.get("expected_payoff", 0.0))
        win_rate = (win_trades / trades * 100.0) if trades > 0 else 0.0

        fitness = 0.0
        if trades >= 10 and net_profit > 0:
            fitness = net_profit * pf * max(0.5, min(sharpe, 5.0)) * (1.0 - (drawdown_pct / 100.0))

        return {
            "name": name,
            "params": params,
            "net_profit": net_profit,
            "profit_factor": pf,
            "sharpe_ratio": sharpe,
            "total_trades": trades,
            "win_trades": win_trades,
            "win_rate": win_rate,
            "drawdown_pct": drawdown_pct,
            "payoff": payoff,
            "fitness": fitness,
            "report_path": str(report_html)
        }
    except Exception as e:
        return {"name": name, "error": str(e), "net_profit": -9999.0}
