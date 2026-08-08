#!/usr/bin/env python3
"""
Session Sweet Spot & Loss Annihilation Suite (3M, 6M, 12M).
Tests precise session windows designed from the 12-month deep autopsy findings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

BASE_PARAMS = {
    "InpOversoldLevel": "28.0",
    "InpOverboughtLevel": "72.0",
    "InpTPRiskMultiple": "4.0",
    "InpMinSLATRMultiple": "1.8",
    "InpEntryRatio": "-0.21",
    "InpBETriggerFibRatio": "0.618",
    "InpUseFibTrailingStop": "true",
    "InpRiskPercent": "1.25"
}

MODELS = [
    ("Model_08-18_NoQuality", {"InpStartHour": "8", "InpEndHour": "18", "InpUseRSIQualityFilter": "false"}),
    ("Model_10-16_NoQuality", {"InpStartHour": "10", "InpEndHour": "16", "InpUseRSIQualityFilter": "false"}),
    ("Model_10-17_NoQuality", {"InpStartHour": "10", "InpEndHour": "17", "InpUseRSIQualityFilter": "false"}),
    ("Model_08-18_WithQuality", {"InpStartHour": "8", "InpEndHour": "18", "InpUseRSIQualityFilter": "true", "InpRSIMinBarsInZone": "2", "InpRSIMinExitDelta": "3.0"}),
    ("Model_10-16_WithQuality", {"InpStartHour": "10", "InpEndHour": "16", "InpUseRSIQualityFilter": "true", "InpRSIMinBarsInZone": "2", "InpRSIMinExitDelta": "3.0"}),
    ("Model_10-17_WithQuality", {"InpStartHour": "10", "InpEndHour": "17", "InpUseRSIQualityFilter": "true", "InpRSIMinBarsInZone": "2", "InpRSIMinExitDelta": "3.0"}),
]

PERIODS = [
    ("3M", "2026.05.01", "2026.08.01"),
    ("6M", "2026.02.01", "2026.08.01"),
    ("12M", "2025.08.01", "2026.08.01")
]

def main():
    print("=== Testing Loss-Optimized Session Windows Across 3M, 6M, 12M ===")
    
    for tf_label, s_date, e_date in PERIODS:
        print(f"\n==================== PERIOD: {tf_label} ({s_date} to {e_date}) ====================")
        print(f"{'Model Name':<26} {'Net Profit':<12} {'PF':<6} {'Sharpe':<8} {'Trades':<8} {'Win%':<7} {'Max DD%':<7}")
        print("-" * 80)
        
        for name, overrides in MODELS:
            params = BASE_PARAMS.copy()
            params.update(overrides)
            
            res = run_single_backtest(params, f"{name}_{tf_label}", deposit=2000.0, from_date=s_date, to_date=e_date)
            net = res.get("net_profit", 0.0)
            pf = res.get("profit_factor", 0.0)
            sharpe = res.get("sharpe_ratio", 0.0)
            trades = res.get("total_trades", 0)
            win_rate = res.get("win_rate", 0.0)
            dd = res.get("drawdown_pct", 0.0)
            
            print(f"{name:<26} {net:>+9.2f} $ {pf:>6.2f} {sharpe:>8.2f} {trades:>8} {win_rate:>6.1f}% {dd:>6.1f}%")

if __name__ == "__main__":
    main()
