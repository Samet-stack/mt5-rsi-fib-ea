#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from pprint import pprint

# Ensure the root of the MT5 project is in sys.path
PROJECT_ROOT = Path("/home/9lx7/mt5-rsi-fib-ea")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Allow higher risk for testing if needed
os.environ["RSIFIB_ALLOW_HIGH_RISK_TESTER"] = "YES"

from tools.auto_optimizer import run_single_backtest

def main():
    deposit = 3000.0
    from_date = "2026.01.01"
    to_date = "2026.07.01"
    
    rsi_min_bars = ["1", "2"]
    entry_ratios = ["-0.21", "0.0", "0.236"]

    results = []

    # Ensure scratch directory exists
    scratch_dir = PROJECT_ROOT / "scratch"
    scratch_dir.mkdir(exist_ok=True)

    for rsi_bars in rsi_min_bars:
        for entry in entry_ratios:
            name = f"monster_RSI{rsi_bars}_Entry{entry}"
            params = {
                "InpCostModelVerified": "true",
                "InpUseSessionFilter": "true",
                "InpStartHour": "8",
                "InpEndHour": "20",
                "InpRSIMinBarsInZone": rsi_bars,
                "InpUseRSIQualityFilter": "false",
                "InpUseMTFTrendFilter": "false",
                "InpEntryRatio": entry,
                "InpRiskPercent": "1.0",
                "InpUseConfidenceSizing": "true",
                "InpGoldenRiskMultiplier": "10.0"
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
            pprint({k: v for k, v in result.items() if k not in ["params"]})
            results.append(result)
                
    # Evaluate best configuration
    best_config = None
    best_profit = -9999.0
    
    for r in results:
        if r.get("error"):
            continue
        
        profit = r.get("net_profit", 0)
        pf = r.get("profit_factor", 0)
        
        # Criteria: profit factor > 1.5
        if pf > 1.5:
            if profit > best_profit:
                best_profit = profit
                best_config = r

    if best_config:
        print("\n--- BEST CONFIGURATION FOUND ---")
        pprint(best_config)
    else:
        print("\n--- NO CONFIGURATION MET CRITERIA ---")
        valid = [r for r in results if not r.get("error")]
        if valid:
            valid.sort(key=lambda x: x.get("net_profit", 0), reverse=True)
            print("Closest result:")
            pprint(valid[0])

if __name__ == "__main__":
    main()
