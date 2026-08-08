#!/usr/bin/env python3
"""
Loss Reduction & Filter Optimization Suite.
Tests MTF Trend Filters, RSI Quality Filters, and Risk Mitigations to eliminate bad Stop Losses.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

BASE_CHAMPION = {
    "InpStartHour": "8",
    "InpEndHour": "18",
    "InpOversoldLevel": "28.0",
    "InpOverboughtLevel": "72.0",
    "InpTPRiskMultiple": "4.0",
    "InpMinSLATRMultiple": "1.8",
    "InpEntryRatio": "-0.21",
    "InpBETriggerFibRatio": "0.618",
    "InpUseFibTrailingStop": "true",
    "InpRiskPercent": "1.25"
}

EXPERIMENTS = [
    ("01_V35_Supreme_Base", {}),
    ("02_MTF_H1_EMA200", {"InpUseMTFTrendFilter": "true", "InpMTFTimeframe": "16385", "InpMTFEMAPeriod": "200"}),
    ("03_MTF_H1_EMA100", {"InpUseMTFTrendFilter": "true", "InpMTFTimeframe": "16385", "InpMTFEMAPeriod": "100"}),
    ("04_MTF_H1_EMA50", {"InpUseMTFTrendFilter": "true", "InpMTFTimeframe": "16385", "InpMTFEMAPeriod": "50"}),
    ("05_MTF_H1_EMA100_RSI50", {"InpUseMTFTrendFilter": "true", "InpMTFTimeframe": "16385", "InpMTFEMAPeriod": "100", "InpMTFUseRSIConfirm": "true"}),
    ("06_M15_EMA200_Trend", {"InpUseMTFTrendFilter": "true", "InpMTFTimeframe": "15", "InpMTFEMAPeriod": "200"}),
    ("07_RSI_Quality_Bars2", {"InpUseRSIQualityFilter": "true", "InpRSIMinBarsInZone": "2", "InpRSIMinExitDelta": "3.0"}),
    ("08_RSI_Quality_Bars3", {"InpUseRSIQualityFilter": "true", "InpRSIMinBarsInZone": "3", "InpRSIMinExitDelta": "4.0"}),
    ("09_MaxConsLoss_1", {"InpMaxConsecutiveLosses": "1"}),
    ("10_MaxDailyTrades_2", {"InpMaxDailyTrades": "2"}),
    ("11_Entry_SlightlyDeeper_-0.25", {"InpEntryRatio": "-0.25"}),
    ("12_SL_Wider_2.0ATR", {"InpMinSLATRMultiple": "2.0"}),
]

def main():
    print("=== Loss Reduction & Filter Investigation (3 Months: 2026.05.01 - 2026.08.01) ===")
    results = []
    
    for name, overrides in EXPERIMENTS:
        params = BASE_CHAMPION.copy()
        params.update(overrides)
        
        print(f"Testing {name:<28} ...", end="", flush=True)
        res = run_single_backtest(params, f"LossOpt_{name}", deposit=2000.0, from_date="2026.05.01", to_date="2026.08.01")
        net = res.get("net_profit", 0.0)
        pf = res.get("profit_factor", 0.0)
        sharpe = res.get("sharpe_ratio", 0.0)
        trades = res.get("total_trades", 0)
        losses = res.get("loss_trades", 0)
        win_rate = res.get("win_rate", 0.0)
        dd = res.get("drawdown_pct", 0.0)
        
        results.append({
            "name": name,
            "net": net,
            "pf": pf,
            "sharpe": sharpe,
            "trades": trades,
            "losses": losses,
            "win_rate": win_rate,
            "dd": dd
        })
        print(f" -> Net: {net:>+7.2f} $ | PF: {pf:>4.2f} | Sharpe: {sharpe:>5.2f} | Trades: {trades:>2} (Pertes: {losses:>2}, WR: {win_rate:>4.1f}%) | DD: {dd:>4.1f}%")

    print("\n" + "="*95)
    print(f"{'Rank':<4} {'Configuration':<30} {'Net Profit':<12} {'PF':<6} {'Sharpe':<8} {'Trades':<8} {'Pertes':<8} {'Win%':<7} {'DD%':<6}")
    print("-" * 95)
    
    # Sort by profit factor and net profit
    results.sort(key=lambda x: (x["pf"], x["net"]), reverse=True)
    for r_idx, r in enumerate(results, 1):
        print(f"{r_idx:<4} {r['name']:<30} {r['net']:>+9.2f} $ {r['pf']:>6.2f} {r['sharpe']:>8.2f} {r['trades']:>8} {r['losses']:>8} {r['win_rate']:>6.1f}% {r['dd']:>5.1f}%")

if __name__ == "__main__":
    main()
