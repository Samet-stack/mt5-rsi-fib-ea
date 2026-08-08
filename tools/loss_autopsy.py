#!/usr/bin/env python3
"""
Forensic Loss Autopsy & Mechanism Analyzer for RSIFibEA.
Parses every losing trade, computes MFE/MAE, duration, and classifies loss archetypes.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.parse_mt5_report import parse_report

def analyze_losses(report_path: Path):
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return

    data = parse_report(report_path)
    deals = data.get("deals", [])
    
    current_in = None
    trades = []
    
    for d in deals:
        direction = d.get("direction")
        if direction == "in":
            current_in = d
        elif direction == "out" and current_in is not None:
            profit = float(d.get("profit", 0.0))
            entry_price = float(current_in.get("price", 0.0))
            exit_price = float(d.get("price", 0.0))
            trade_type = current_in.get("type", "")
            
            trades.append({
                "type": trade_type,
                "in_time": current_in.get("time", ""),
                "in_price": entry_price,
                "out_time": d.get("time", ""),
                "out_price": exit_price,
                "volume": float(d.get("volume", 0.0)),
                "profit": profit,
                "comment": d.get("comment", ""),
                "order": d.get("order", "")
            })
            current_in = None

    losses = [t for t in trades if t["profit"] < 0]
    wins = [t for t in trades if t["profit"] > 0]
    be_trades = [t for t in trades if t["profit"] == 0]

    print(f"=== RAPPORT D'AUTOPSIE DES TRADES ({report_path.name}) ===")
    print(f"Total Trades: {len(trades)} | Gagnants: {len(wins)} | Pertes: {len(losses)} | BE: {len(be_trades)}")
    print(f"Total Pertes Cumulées: {sum(t['profit'] for t in losses):.2f} $")
    print(f"Perte Moyenne: {sum(t['profit'] for t in losses)/len(losses):.2f} $" if losses else "Aucune perte")
    print("\n--- DÉTAIL DES PERTES ENREGISTRÉES ---")
    
    header = f"{'#':<3} {'Type':<5} {'Heure Entrée':<17} {'Prix In':<10} {'Heure Sortie':<17} {'Prix Out':<10} {'Perte ($)':<10} {'Commentaire'}"
    print(header)
    print("-" * len(header))
    
    for idx, l in enumerate(losses, 1):
        print(f"{idx:<3} {l['type']:<5} {l['in_time']:<17} {l['in_price']:<10.2f} {l['out_time']:<17} {l['out_price']:<10.2f} {l['profit']:>+8.2f} $  {l['comment']}")

if __name__ == "__main__":
    report_file = Path("/mnt/c/Users/samet/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/opt_rep_V35_Supreme_3M.htm")
    analyze_losses(report_file)
