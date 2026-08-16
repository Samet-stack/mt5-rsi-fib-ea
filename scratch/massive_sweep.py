#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("/home/9lx7/mt5-rsi-fib-ea")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["RSIFIB_MT5_DATA_DIR"] = "/mnt/c/Users/samet/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075"
os.environ["RSIFIB_MT5_CONFIG_DIR"] = "/mnt/c/Users/samet/AppData/Local/RSIFibEA"
os.environ["RSIFIB_ALLOW_HIGH_RISK_TESTER"] = "YES"

from tools.auto_optimizer import run_single_backtest

def main():
    deposit = 3000.0
    from_date = "2026.01.01"
    to_date = "2026.07.01" # Full 6 months
    
    rsi_quality = ["true", "false"]
    mtf_trend = ["true", "false"]
    start_hours = ["8", "10"]
    end_hours = ["16", "20"]
    entry_ratios = ["-0.21", "0.0"]
    trade_dirs = ["0", "2"] # Both, Short-Only

    total_tests = len(rsi_quality) * len(mtf_trend) * len(start_hours) * len(end_hours) * len(entry_ratios) * len(trade_dirs)
    print(f"Starting massive grid search with {total_tests} configurations over 6 months...")
    
    results = []
    count = 0

    for rsi in rsi_quality:
        for mtf in mtf_trend:
            for sh in start_hours:
                for eh in end_hours:
                    for er in entry_ratios:
                        for td in trade_dirs:
                            count += 1
                            name = f"g_rsi{rsi[0]}_mtf{mtf[0]}_sh{sh}_eh{eh}_er{er}_td{td}"
                            params = {
                                "InpCostModelVerified": "true",
                                "InpUseSessionFilter": "true",
                                "InpStartHour": sh,
                                "InpEndHour": eh,
                                "InpTradeDirection": td,
                                "InpRSIMinBarsInZone": "2",
                                "InpUseRSIQualityFilter": rsi,
                                "InpUseMTFTrendFilter": mtf,
                                "InpEntryRatio": er,
                                "InpRiskPercent": "1.0",
                                "InpUseConfidenceSizing": "true",
                                "InpGoldenRiskMultiplier": "10.0"
                            }
                            
                            print(f"[{count}/{total_tests}] Running: {name}")
                            result = run_single_backtest(
                                params=params, 
                                name=name, 
                                deposit=deposit, 
                                from_date=from_date, 
                                to_date=to_date
                            )
                            
                            if not result.get("error"):
                                res_summary = {
                                    "name": name,
                                    "params": params,
                                    "trades": result.get("total_trades", 0),
                                    "pf": result.get("profit_factor", 0),
                                    "net": result.get("net_profit", 0)
                                }
                                results.append(res_summary)
                                print(f"  -> Trades: {res_summary['trades']}, PF: {res_summary['pf']}, Net: {res_summary['net']}")
                            else:
                                print("  -> Error.")
                                
    # Save all results to a JSON file
    output_file = "/home/9lx7/mt5-rsi-fib-ea/scratch/massive_sweep_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved {len(results)} results to {output_file}")
    
    # Filter best
    valid = [r for r in results if r['trades'] >= 10 and r['pf'] > 1.3]
    valid.sort(key=lambda x: x['net'], reverse=True)
    
    print("\n--- TOP 5 CONFIGURATIONS (Trades >= 10, PF > 1.3) ---")
    for v in valid[:5]:
        print(f"Trades: {v['trades']}, PF: {v['pf']}, Net: {v['net']}")
        print(v['params'])

if __name__ == "__main__":
    main()
