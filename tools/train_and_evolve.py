#!/usr/bin/env python3
"""
Systematic Optimization & Training Runner for RSIFibEA (Quant Research Edition).
Tests scientifically curated parameter candidates on XAUUSD M15 (2000 USD Capital).
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.auto_optimizer import run_single_backtest

CANDIDATES = [
    # 1. Baseline V3.4 (2k Capital)
    {
        "name": "V34_Base_2k",
        "params": {
            "InpTPRiskMultiple": "4.0", "InpMinSLATRMultiple": "1.8",
            "InpStartHour": "7", "InpEndHour": "19", "InpEntryRatio": "-0.21",
            "InpBETriggerFibRatio": "0.618"
        }
    },
    # 2. Preset A: Balanced Gold M15 (Subagent Recommendation)
    {
        "name": "PresetA_Balanced_Gold",
        "params": {
            "InpEntryRatio": "-0.29", "InpMinSLATRMultiple": "1.75",
            "InpTPRiskMultiple": "3.5", "InpStartHour": "8", "InpEndHour": "19",
            "InpBETriggerFibRatio": "0.618"
        }
    },
    # 3. Preset B: High-Asymmetry Runner (Extension 4.5R)
    {
        "name": "PresetB_Asymmetry_Runner_4.5R",
        "params": {
            "InpEntryRatio": "-0.382", "InpMinSLATRMultiple": "2.0",
            "InpTPRiskMultiple": "4.5", "InpStartHour": "9", "InpEndHour": "18",
            "InpBETriggerFibRatio": "0.786"
        }
    },
    # 4. Preset C: High-Frequency Intra-Session (TP 3.0R)
    {
        "name": "PresetC_IntraSession_3.0R",
        "params": {
            "InpEntryRatio": "-0.21", "InpMinSLATRMultiple": "1.5",
            "InpTPRiskMultiple": "3.0", "InpStartHour": "7", "InpEndHour": "20",
            "InpBETriggerFibRatio": "0.618"
        }
    },
    # 5. TP 4.5R Expansion on Entry -0.21
    {
        "name": "TP4.5_Entry-0.21_SL1.8",
        "params": {
            "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8",
            "InpStartHour": "7", "InpEndHour": "19", "InpEntryRatio": "-0.21"
        }
    },
    # 6. TP 5.0R Expansion on Entry -0.21
    {
        "name": "TP5.0_Entry-0.21_SL1.8",
        "params": {
            "InpTPRiskMultiple": "5.0", "InpMinSLATRMultiple": "1.8",
            "InpStartHour": "7", "InpEndHour": "19", "InpEntryRatio": "-0.21"
        }
    },
    # 7. Deep Retracement Entry -0.35 + TP 4.0R
    {
        "name": "DeepEntry-0.35_TP4.0",
        "params": {
            "InpEntryRatio": "-0.35", "InpMinSLATRMultiple": "1.8",
            "InpTPRiskMultiple": "4.0", "InpStartHour": "7", "InpEndHour": "19"
        }
    },
    # 8. Deep Retracement Entry -0.35 + TP 4.5R
    {
        "name": "DeepEntry-0.35_TP4.5",
        "params": {
            "InpEntryRatio": "-0.35", "InpMinSLATRMultiple": "1.8",
            "InpTPRiskMultiple": "4.5", "InpStartHour": "7", "InpEndHour": "19"
        }
    },
    # 9. Golden Retracement Entry -0.382 + TP 4.0R + SL 1.75
    {
        "name": "Golden-0.382_TP4.0_SL1.75",
        "params": {
            "InpEntryRatio": "-0.382", "InpMinSLATRMultiple": "1.75",
            "InpTPRiskMultiple": "4.0", "InpStartHour": "8", "InpEndHour": "19"
        }
    },
    # 10. London-NY Overlap Session 08:00 - 18:00
    {
        "name": "Session_08-18_TP4.0",
        "params": {
            "InpStartHour": "8", "InpEndHour": "18",
            "InpTPRiskMultiple": "4.0", "InpMinSLATRMultiple": "1.8", "InpEntryRatio": "-0.21"
        }
    },
    # 11. London-NY Overlap Session 08:00 - 18:00 + TP 4.5R
    {
        "name": "Session_08-18_TP4.5",
        "params": {
            "InpStartHour": "8", "InpEndHour": "18",
            "InpTPRiskMultiple": "4.5", "InpMinSLATRMultiple": "1.8", "InpEntryRatio": "-0.21"
        }
    },
    # 12. Wide SL 2.2 + TP 5.0
    {
        "name": "WideSL2.2_TP5.0",
        "params": {
            "InpMinSLATRMultiple": "2.2", "InpTPRiskMultiple": "5.0",
            "InpStartHour": "7", "InpEndHour": "19", "InpEntryRatio": "-0.21"
        }
    },
    # 13. High-Discipline RSI Zone (28/72) + TP 4.0R
    {
        "name": "RSI_Zone28-72_TP4.0",
        "params": {
            "InpOversoldLevel": "28.0", "InpOverboughtLevel": "72.0",
            "InpTPRiskMultiple": "4.0", "InpMinSLATRMultiple": "1.8", "InpEntryRatio": "-0.21"
        }
    },
    # 14. Responsive RSI Zone (32/68) + TP 4.0R
    {
        "name": "RSI_Zone32-68_TP4.0",
        "params": {
            "InpOversoldLevel": "32.0", "InpOverboughtLevel": "68.0",
            "InpTPRiskMultiple": "4.0", "InpMinSLATRMultiple": "1.8", "InpEntryRatio": "-0.21"
        }
    }
]

def main():
    print(f"=== Starting High-Precision Strategy Training ({len(CANDIDATES)} candidates) ===")
    results: List[Dict[str, Any]] = []

    for i, c in enumerate(CANDIDATES, 1):
        name = c["name"]
        params = c["params"]
        print(f"[{i:02d}/{len(CANDIDATES)}] Testing {name:<28} ...", end="", flush=True)
        res = run_single_backtest(params, name, deposit=2000.0, from_date="2026.05.01", to_date="2026.08.01")
        results.append(res)
        net = res.get("net_profit", 0.0)
        pf = res.get("profit_factor", 0.0)
        sharpe = res.get("sharpe_ratio", 0.0)
        trades = res.get("total_trades", 0)
        win_rate = res.get("win_rate", 0.0)
        dd = res.get("drawdown_pct", 0.0)
        fitness = res.get("fitness", 0.0)
        print(f" -> Net: {net:>+8.2f} $ | PF: {pf:>4.2f} | Sharpe: {sharpe:>5.2f} | Trades: {trades:>3} (WR: {win_rate:>4.1f}%) | DD: {dd:>4.1f}% | Fit: {fitness:>6.1f}")

    print("\n" + "="*95)
    print("🏆 RANKED LEADERBOARD (Sorted by Composite Fitness / Total Profit):")
    print("="*95)
    valid_results = [r for r in results if r.get("net_profit", -999) > 0 and r.get("total_trades", 0) >= 10]
    valid_results.sort(key=lambda x: (x.get("fitness", 0), x.get("net_profit", 0)), reverse=True)

    header = f"{'Rank':<5} {'Candidate Name':<30} {'Net Profit':<13} {'PF':<6} {'Sharpe':<8} {'Trades':<8} {'Win%':<7} {'DD%':<7} {'Fitness':<8}"
    print(header)
    print("-" * len(header))
    for idx, r in enumerate(valid_results, 1):
        print(f"{idx:<5} {r['name']:<30} {r['net_profit']:>+8.2f} $    {r['profit_factor']:>5.2f} {r['sharpe_ratio']:>7.2f} {r['total_trades']:>7} {r['win_rate']:>6.1f}% {r['drawdown_pct']:>6.1f}% {r['fitness']:>8.1f}")

if __name__ == "__main__":
    main()
