#!/usr/bin/env python3
"""Legacy fine-tuning sweep on exposed windows; no forward-performance claim."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

FINE_VARIANTS = [
    # 1. Stagnation Exit + 10-17 Session + Risk 3.0%
    {"name": "FT01_Stagnation_10-17_Risk3.0", "params": {
        "InpRiskPercent": "3.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 2. Stagnation Exit + 10-17 Session + Risk 3.5%
    {"name": "FT02_Stagnation_10-17_Risk3.5", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 3. Stagnation Exit + 09-17 Session + Risk 3.5%
    {"name": "FT03_Stagnation_09-17_Risk3.5", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "9", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 4. Stagnation Exit + 10-17 Session + Risk 4.0%
    {"name": "FT04_Stagnation_10-17_Risk4.0_Target600", "params": {
        "InpRiskPercent": "4.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 5. Stagnation Exit + 10-17 Session + Risk 3.5% + TP 5.5R
    {"name": "FT05_Stagnation_10-17_Risk3.5_TP5.5", "params": {
        "InpRiskPercent": "3.5", "InpTPRiskMultiple": "5.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 6. Stagnation Exit + 10-17 Session + Risk 4.0% + TP 5.5R
    {"name": "FT06_Stagnation_10-17_Risk4.0_TP5.5", "params": {
        "InpRiskPercent": "4.0", "InpTPRiskMultiple": "5.5", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 7. Stagnation Exit (6 bars) + 10-17 Session + Risk 4.0%
    {"name": "FT07_Stagnation6Bars_10-17_Risk4.0", "params": {
        "InpRiskPercent": "4.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "false",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "6",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }},
    # 8. Stagnation Exit + Sweep Buffer + 10-17 Session + Risk 4.0%
    {"name": "FT08_Stagnation_Sweep_10-17_Risk4.0", "params": {
        "InpRiskPercent": "4.0", "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
        "InpEntryRatio": "-0.21", "InpStartHour": "10", "InpEndHour": "17",
        "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0", "InpUseRSIQualityFilter": "true",
        "InpUseMarketStructure": "false", "InpUseSweepBuffer": "true", "InpSweepLookbackBars": "5", "InpSweepBufferATR": "0.3",
        "InpUseStagnationExit": "true", "InpStagnationMaxBars": "8",
        "InpBETriggerFibRatio": "0.618", "InpUseFibTrailingStop": "true"
    }}
]

def main():
    print("=" * 110)
    print("LEGACY FINE-TUNING SWEEP: RESULTS ARE EXPLORATORY ONLY")
    print("=" * 110)

    for v in FINE_VARIANTS:
        name = v["name"]
        params = v["params"]
        print(f"\nEvaluating {name}...")
        
        # 3M
        r3 = run_single_backtest(params, f"{name}_3M", deposit=2000.0, from_date="2026.05.01", to_date="2026.08.01")
        print(f"  • 3M  : Net: {r3.get('net_profit',0):>+8.2f} $ | PF: {r3.get('profit_factor',0):>5.2f} | Sharpe: {r3.get('sharpe_ratio',0):>5.2f} | Trades: {r3.get('total_trades',0):>2} | WR: {r3.get('win_rate',0):>4.1f}% | DD: {r3.get('drawdown_pct',0):>4.1f}%")
        
        # 6M
        r6 = run_single_backtest(params, f"{name}_6M", deposit=2000.0, from_date="2026.02.01", to_date="2026.08.01")
        print(f"  • 6M  : Net: {r6.get('net_profit',0):>+8.2f} $ | PF: {r6.get('profit_factor',0):>5.2f} | Sharpe: {r6.get('sharpe_ratio',0):>5.2f} | Trades: {r6.get('total_trades',0):>2} | WR: {r6.get('win_rate',0):>4.1f}% | DD: {r6.get('drawdown_pct',0):>4.1f}%")
        
        # 12M
        r12 = run_single_backtest(params, f"{name}_12M", deposit=2000.0, from_date="2025.08.01", to_date="2026.08.01")
        print(f"  • 12M : Net: {r12.get('net_profit',0):>+8.2f} $ | PF: {r12.get('profit_factor',0):>5.2f} | Sharpe: {r12.get('sharpe_ratio',0):>5.2f} | Trades: {r12.get('total_trades',0):>2} | WR: {r12.get('win_rate',0):>4.1f}% | DD: {r12.get('drawdown_pct',0):>4.1f}%")

if __name__ == "__main__":
    main()
