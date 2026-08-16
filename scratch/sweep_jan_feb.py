#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from pprint import pprint

# Ensure the root of the MT5 project is in sys.path
PROJECT_ROOT = Path("/home/9lx7/mt5-rsi-fib-ea")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["RSIFIB_ALLOW_HIGH_RISK_TESTER"] = "YES"

from tools.auto_optimizer import run_single_backtest

def main():
    deposit = 3000.0
    from_date = "2026.01.01"
    to_date = "2026.03.01" # Jan + Feb
    
    rsi_quality = ["true", "false"]
    mtf_trend = ["true", "false"]
    end_hours = ["20", "16"]
    trade_dirs = ["0", "2"] # 0 = Both, 2 = Short Only

    results = []

    for rsi in rsi_quality:
        for mtf in mtf_trend:
            for eh in end_hours:
                for td in trade_dirs:
                    name = f"opt_rsi{rsi}_mtf{mtf}_eh{eh}_td{td}"
                    params = {
                        "InpCostModelVerified": "true",
                        "InpUseSessionFilter": "true",
                        "InpStartHour": "10",
                        "InpEndHour": eh,
                        "InpTradeDirection": td,
                        "InpRSIMinBarsInZone": "2",
                        "InpUseRSIQualityFilter": rsi,
                        "InpUseMTFTrendFilter": mtf,
                        "InpEntryRatio": "-0.21",
                        "InpRiskPercent": "1.0",
                        "InpUseConfidenceSizing": "true",
                        "InpGoldenRiskMultiplier": "10.0"
                    }
                    
                    print(f"Running: {name}")
                    result = run_single_backtest(
                        params=params, 
                        name=name, 
                        deposit=deposit, 
                        from_date=from_date, 
                        to_date=to_date
                    )
                    
                    if not result.get("error"):
                        results.append(result)
                        print(f"Trades: {result.get('total_trades')}, PF: {result.get('profit_factor')}, Net: {result.get('net_profit')}")
                    else:
                        print("Error running backtest.")
                        
    # Filter for trades > 2 and profit > 0
    valid = [r for r in results if r.get('total_trades', 0) > 2 and r.get('net_profit', 0) > 0]
    valid.sort(key=lambda x: x.get('net_profit', 0), reverse=True)
    
    print("\n--- BEST BALANCED CONFIGURATIONS FOR JAN-FEB ---")
    for v in valid[:3]:
        print(f"Name: {v['name']}, Trades: {v['total_trades']}, PF: {v['profit_factor']}, Net: {v['net_profit']}")
        print(v['params'])

if __name__ == "__main__":
    main()
