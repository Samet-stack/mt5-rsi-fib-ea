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

MT5_TERMINAL = "/mnt/c/Program Files/MetaTrader 5/terminal64.exe"
MT5_APPDATA = Path("/mnt/c/Users/samet/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075")
LOCAL_INI_DIR = Path("/mnt/c/Users/samet/AppData/Local/RSIFibEA")
PROFILES_TESTER_DIR = MT5_APPDATA / "MQL5/Profiles/Tester"

BASE_TEMPLATE = {
    "InpDemoOnly": "true",
    "InpMagicNumber": "20260806",
    "InpRiskPercent": "1.25",
    "InpMaxDailyLossPct": "5.0",
    "InpMaxDailyTrades": "5",
    "InpMaxConsecutiveLosses": "3",
    "InpMaxSpreadPoints": "0",
    "InpMaxSpreadRiskPct": "25.0",
    "InpCloseUnprotectedPosition": "true",
    "InpStateWatchdogMs": "1000",
    "InpCostModelVerified": "true",
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
    "InpUseMTFTrendFilter": "false",
    "InpMTFTimeframe": "16385",
    "InpMTFEMAPeriod": "200",
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
    "InpUseBreakEven": "true",
    "InpBETriggerFibRatio": "0.618",
    "InpBEOffsetTicks": "2",
    "InpUseFibTrailingStop": "true",
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

def generate_set_file(params: Dict[str, Any], filename: str) -> Path:
    PROFILES_TESTER_DIR.mkdir(parents=True, exist_ok=True)
    set_path = PROFILES_TESTER_DIR / filename
    full_params = dict(BASE_TEMPLATE)
    full_params.update(params)
    with open(set_path, "w", encoding="utf-8") as f:
        f.write(f"; Auto-Generated Optimization Preset: {filename}\n")
        for k, v in full_params.items():
            f.write(f"{k}={v}\n")
    return set_path

def generate_ini_file(set_filename: str, report_name: str, deposit: float, from_date: str, to_date: str) -> Path:
    LOCAL_INI_DIR.mkdir(parents=True, exist_ok=True)
    ini_path = LOCAL_INI_DIR / "auto_opt.ini"
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
    generate_ini_file(set_filename, report_name, deposit, from_date, to_date)
    
    report_html = MT5_APPDATA / f"{report_name}.htm"
    if report_html.exists():
        try:
            report_html.unlink()
        except Exception:
            pass

    cmd = [
        MT5_TERMINAL,
        r"/config:C:\Users\samet\AppData\Local\RSIFibEA\auto_opt.ini"
    ]
    subprocess.run(cmd)

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
