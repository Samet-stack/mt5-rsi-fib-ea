#!/usr/bin/env python3
"""
Test V3.6 Ultra-Shield (Loss-Reduction Champion) across 3M, 6M, and 12M.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

V36_SHIELD_PARAMS = {
    "InpStartHour": "8",
    "InpEndHour": "18",
    "InpOversoldLevel": "28.0",
    "InpOverboughtLevel": "72.0",
    "InpUseRSIQualityFilter": "true",
    "InpRSIMinBarsInZone": "2",
    "InpRSIMinExitDelta": "3.0",
    "InpTPRiskMultiple": "4.0",
    "InpMinSLATRMultiple": "1.8",
    "InpEntryRatio": "-0.21",
    "InpBETriggerFibRatio": "0.618",
    "InpUseFibTrailingStop": "true",
    "InpRiskPercent": "1.25"
}

PERIODS = [
    ("V36_Shield_3M", "2026.05.01", "2026.08.01", "3 Mois"),
    ("V36_Shield_6M", "2026.02.01", "2026.08.01", "6 Mois"),
    ("V36_Shield_12M", "2025.08.01", "2026.08.01", "1 An (12 Mois)")
]

def main():
    print("=== Testing V3.6 Ultra-Shield Multi-Month Loss-Reduction Stress Test ===")
    for name, start_d, end_d, label in PERIODS:
        print(f"\n--- Testing Period: {label} ({start_d} à {end_d}) ---")
        res = run_single_backtest(V36_SHIELD_PARAMS, name, deposit=2000.0, from_date=start_d, to_date=end_d)
        net = res.get("net_profit", 0.0)
        pf = res.get("profit_factor", 0.0)
        sharpe = res.get("sharpe_ratio", 0.0)
        trades = res.get("total_trades", 0)
        wins = res.get("win_trades", 0)
        win_rate = res.get("win_rate", 0.0)
        dd = res.get("drawdown_pct", 0.0)
        payoff = res.get("payoff", 0.0)
        print(f"Result {label}:")
        print(f"  Profit Net       : {net:>+9.2f} $")
        print(f"  Profit Factor    : {pf:>9.2f}")
        print(f"  Ratio de Sharpe  : {sharpe:>9.2f}")
        print(f"  Total Trades     : {trades:>9} (Gagnants: {wins}, WR: {win_rate:.1f}%)")
        print(f"  Gain Moyen/Trade : {payoff:>+9.2f} $")
        print(f"  Max Drawdown     : {dd:>9.2f} %")

if __name__ == "__main__":
    main()
