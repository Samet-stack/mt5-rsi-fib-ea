#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from pprint import pprint

# Ensure the root of the MT5 project is in sys.path
PROJECT_ROOT = Path("/home/9lx7/mt5-rsi-fib-ea")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.auto_optimizer import run_single_backtest

def main():
    deposit = 3000.0
    from_date = "2026.05.15"
    to_date = "2026.08.15"
    
    # Grid search combinations
    margin_usage_pcts = ["35.0", "40.0"]
    ema_periods = ["200", "100"]
    exit_deltas = ["4.0", "3.0"]

    results = []

    for margin in margin_usage_pcts:
        for ema in ema_periods:
            for exit_delta in exit_deltas:
                name = f"freq_M{margin}_E{ema}_D{exit_delta}"
                params = {
                    "InpCostModelVerified": "true",
                    "InpRSIMinBarsInZone": "2",
                    "InpUseMTFTrendFilter": "true",
                    "InpMaxFreeMarginUsagePct": margin,
                    "InpMTFEMAPeriod": ema,
                    "InpRSIMinExitDelta": exit_delta,
                    "InpRiskPercent": "1.0",
                    "InpUseConfidenceSizing": "true",
                    "InpGoldenRiskMultiplier": "10.0",
                    "InpUseSessionFilter": "false"
                }
                
                print(f"Running sweep for {name} with params: {params}")
                result = run_single_backtest(
                    params=params, 
                    name=name, 
                    deposit=deposit, 
                    from_date=from_date, 
                    to_date=to_date
                )
                print(f"Result for {name}:")
                pprint(result)
                results.append(result)
                
    # Evaluate best configuration
    best_config = None
    best_profit = -9999.0
    
    for r in results:
        if r.get("error"):
            continue
        
        profit = r.get("net_profit", 0)
        pf = r.get("profit_factor", 0)
        
        # Criteria: net profit > 250, profit factor > 1.5
        if profit > 250.0 and pf > 1.5:
            if profit > best_profit:
                best_profit = profit
                best_config = r

    if best_config:
        print("\n--- BEST CONFIGURATION FOUND ---")
        pprint(best_config)
    else:
        print("\n--- NO CONFIGURATION MET CRITERIA ---")
        # Print best overall just to see
        valid = [r for r in results if not r.get("error")]
        if valid:
            valid.sort(key=lambda x: x.get("net_profit", 0), reverse=True)
            print("Closest result:")
            pprint(valid[0])

if __name__ == "__main__":
    main()
