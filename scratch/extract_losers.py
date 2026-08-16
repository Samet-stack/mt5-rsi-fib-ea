import json
import csv
from pathlib import Path

def main():
    json_path = Path('/home/9lx7/mt5-rsi-fib-ea/scratch/monster_adjusted.json')
    data = json.loads(json_path.read_text())
    
    # parse_mt5_report returns a list of scenarios or just a dict, let's extract the normal scenario positions.
    # From previous calls, it returns a list of dictionaries with 'scenarios' -> 'normal' -> 'positions'
    
    if isinstance(data, list):
        data = data[0]
        
    positions = data.get('scenarios', {}).get('normal', {}).get('positions', [])
    if not positions:
        print("No positions found.")
        return
        
    losers = [p for p in positions if p.get('native_profit', 0) < 0]
    
    print(f"Total trades: {len(positions)}")
    print(f"Total losers: {len(losers)}")
    
    csv_path = Path('/home/9lx7/mt5-rsi-fib-ea/scratch/losing_trades.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["time", "side", "profit", "duration_approx"])
        
        for p in losers:
            writer.writerow([
                p.get("first_time", ""),
                p.get("side", ""),
                p.get("native_profit", ""),
                "N/A" # duration not directly available in basic parser output without deals matching
            ])
            
    print(f"Saved {len(losers)} losing trades to {csv_path}")

if __name__ == "__main__":
    main()
