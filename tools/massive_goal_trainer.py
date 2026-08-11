#!/usr/bin/env python3
"""Legacy exploratory parameter sweep retained for reproducibility.

It searches already exposed windows and cannot establish future performance.
The cost-model gate remains mandatory and high-risk variants are tester-only.
"""

import sys
import json
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

# Parameter Search Space
GRID = {
    "InpRiskPercent": ["2.0", "2.5", "3.0", "3.5"],
    "InpTPRiskMultiple": ["4.0", "4.5", "5.0", "5.5"],
    "InpMinSLATRMultiple": ["1.6", "1.8", "2.0"],
    "InpEntryRatio": ["-0.21", "-0.25", "-0.18"],
    "InpStartHour": ["9", "10"],
    "InpEndHour": ["16", "17", "18"],
    "InpOversoldLevel": ["28.0", "30.0"],
    "InpOverboughtLevel": ["72.0", "70.0"],
    "InpUseRSIQualityFilter": ["true", "false"],
    "InpUseMarketStructure": ["true", "false"],
    "InpUseSweepBuffer": ["true", "false"],
    "InpUseStagnationExit": ["true", "false"],
    "InpBETriggerFibRatio": ["0.618", "0.786", "1.000"],
    "InpUseFibTrailingStop": ["true"]
}

# Curated High-Impact Variants to test first
FOCUSED_VARIANTS = [
    # Baseline V3.7 with scaled risk
    {"name": "G01_Risk2.5_TP4.5_Base", "params": {
        "InpRiskPercent": "2.5", "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G02_Risk3.0_TP5.0_Runner", "params": {
        "InpRiskPercent": "3.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G03_Risk3.5_TP5.5_Target600", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G04_Risk2.5_StructureBOS_On", "params": {
        "InpRiskPercent": "2.5", "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "true", "InpStructureSwingBars": "5", "InpRequireStructureBOS": "true",
        "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G05_Risk3.0_SweepBuffer_On", "params": {
        "InpRiskPercent": "3.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "true", "InpSweepLookbackBars": "5", "InpSweepBufferATR": "0.3",
        "InpUseStagnationExit": "false", "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G06_Risk3.0_StagnationExit_On", "params": {
        "InpRiskPercent": "3.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "16",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G07_Risk3.0_Hours_09-17_Quality", "params": {
        "InpRiskPercent": "3.0", "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "9", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G08_Risk3.5_Hours_09-18_Quality", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "9", "InpEndHour": "18",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G09_Risk3.5_BE_0.786_MoreBreathing", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.786", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G10_Risk3.5_DeeperEntry_-0.25", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.25", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G11_Risk3.5_FullCombo_AllShields", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "true", "InpStructureSwingBars": "5", "InpRequireStructureBOS": "true",
        "InpUseSweepBuffer": "true", "InpSweepLookbackBars": "5", "InpSweepBufferATR": "0.3",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    {"name": "G12_Risk4.0_SupremeAggressive_600Target", "params": {
        "InpRiskPercent": "4.0", "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false", "InpUseStagnationExit": "false",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }}
]

def main():
    print("=" * 110)
    print("LEGACY EXPLORATORY SWEEP: NO PERFORMANCE TARGET OR FORWARD CLAIM")
    print("=" * 110)
    
    results_3m = []
    
    for v in FOCUSED_VARIANTS:
        name = v["name"]
        params = v["params"]
        print(f"Testing {name:<35} (3M: 2026.05.01 - 2026.08.01)...", end="", flush=True)
        res = run_single_backtest(params, name, deposit=2000.0, from_date="2026.05.01", to_date="2026.08.01")
        net = res.get("net_profit", 0.0)
        pf = res.get("profit_factor", 0.0)
        sharpe = res.get("sharpe_ratio", 0.0)
        trades = res.get("total_trades", 0)
        wins = res.get("win_trades", 0)
        win_rate = res.get("win_rate", 0.0)
        dd = res.get("drawdown_pct", 0.0)
        print(f" -> Net: {net:>+8.2f} $ | PF: {pf:>5.2f} | Sharpe: {sharpe:>6.2f} | Trades: {trades:>2} (WR: {win_rate:>4.1f}%) | DD: {dd:>4.1f}%")
        
        results_3m.append({
            "name": name,
            "params": params,
            "net": net,
            "pf": pf,
            "sharpe": sharpe,
            "trades": trades,
            "wins": wins,
            "win_rate": win_rate,
            "dd": dd
        })

    # Sort results
    results_3m.sort(key=lambda x: (x["net"] >= 400.0, x["pf"], x["net"]), reverse=True)
    
    print("\n" + "=" * 110)
    print(f"{'Rank':<5} {'Configuration':<36} {'Net Profit':<12} {'PF':<6} {'Sharpe':<8} {'Trades':<8} {'Win%':<7} {'DD%':<6}")
    print("-" * 110)
    for idx, r in enumerate(results_3m, 1):
        print(f"{idx:<5} {r['name']:<36} {r['net']:>+9.2f} $ {r['pf']:>6.2f} {r['sharpe']:>8.2f} {r['trades']:>8} {r['win_rate']:>6.1f}% {r['dd']:>5.1f}%")

    # Re-evaluate the top three in longer, already exposed windows.
    top_champions = results_3m[:3]
    print("\n" + "=" * 110)
    print("MULTI-MONTH SENSITIVITY CHECK FOR TOP THREE IN-SAMPLE RESULTS")
    print("=" * 110)
    
    for c in top_champions:
        c_name = c["name"]
        c_params = c["params"]
        print(f"\n--- Candidate: {c_name} ---")
        
        # 6M
        res_6m = run_single_backtest(c_params, f"{c_name}_6M", deposit=2000.0, from_date="2026.02.01", to_date="2026.08.01")
        print(f"  • 6 Mois  : Net: {res_6m.get('net_profit',0):>+8.2f} $ | PF: {res_6m.get('profit_factor',0):>5.2f} | Sharpe: {res_6m.get('sharpe_ratio',0):>5.2f} | Trades: {res_6m.get('total_trades',0):>2} | WR: {res_6m.get('win_rate',0):>4.1f}% | DD: {res_6m.get('drawdown_pct',0):>4.1f}%")
        
        # 12M
        res_12m = run_single_backtest(c_params, f"{c_name}_12M", deposit=2000.0, from_date="2025.08.01", to_date="2026.08.01")
        print(f"  • 12 Mois : Net: {res_12m.get('net_profit',0):>+8.2f} $ | PF: {res_12m.get('profit_factor',0):>5.2f} | Sharpe: {res_12m.get('sharpe_ratio',0):>5.2f} | Trades: {res_12m.get('total_trades',0):>2} | WR: {res_12m.get('win_rate',0):>4.1f}% | DD: {res_12m.get('drawdown_pct',0):>4.1f}%")

if __name__ == "__main__":
    main()
