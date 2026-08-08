#!/usr/bin/env python3
"""
Comprehensive 12-Month Deep Loss Autopsy for RSIFibEA on Gold M15.
Extracts every losing trade over 1 full year and analyzes hour, day, direction, duration, and root cause.
"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.parse_mt5_report import parse_report

def deep_autopsy(report_path: Path):
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
            
            in_time_str = current_in.get("time", "")
            out_time_str = d.get("time", "")
            
            dt_in = None
            dt_out = None
            try:
                dt_in = datetime.strptime(in_time_str, "%Y.%m.%d %H:%M:%S")
                dt_out = datetime.strptime(out_time_str, "%Y.%m.%d %H:%M:%S")
                duration_min = (dt_out - dt_in).total_seconds() / 60.0
            except Exception:
                duration_min = 0.0
                
            trades.append({
                "type": trade_type,
                "in_time": in_time_str,
                "dt_in": dt_in,
                "in_price": entry_price,
                "out_time": out_time_str,
                "dt_out": dt_out,
                "out_price": exit_price,
                "duration_min": duration_min,
                "volume": float(d.get("volume", 0.0)),
                "profit": profit,
                "comment": d.get("comment", ""),
                "order": d.get("order", "")
            })
            current_in = None

    losses = [t for t in trades if t["profit"] < 0]
    wins = [t for t in trades if t["profit"] > 0]
    
    # Real losses vs Break-Even micro-friction losses (< -1.00$)
    be_losses = [t for t in losses if t["profit"] > -1.00]
    hard_losses = [t for t in losses if t["profit"] <= -1.00]

    print("=" * 100)
    print(f"🔬 AUTOPSIE SCIENTIFIQUE DES PERTES SUR 1 AN COMPLET (12 MOIS - 98 TRADES)")
    print("=" * 100)
    print(f"Total Trades Exécutés : {len(trades)}")
    print(f"Trades Gagnants        : {len(wins)} (Profit Brut: +{sum(t['profit'] for t in wins):.2f} $)")
    print(f"Trades Perdants        : {len(losses)} (Perte Brute: {sum(t['profit'] for t in losses):.2f} $)")
    print(f"  ├─ Faux Perdants (BE sécurisés < 1$)  : {len(be_losses)} trades (Perte totale: {sum(t['profit'] for t in be_losses):.2f} $)")
    print(f"  └─ Vraies Pertes (Stop Loss plein > 1$) : {len(hard_losses)} trades (Perte totale: {sum(t['profit'] for t in hard_losses):.2f} $)")
    print(f"Profit Net Réalisé     : +{sum(t['profit'] for t in trades):.2f} $")
    print(f"Taux de Réussite Réel  : {len(wins)/len(trades)*100:.1f} % (Excluant BE: {len(wins)/(len(wins)+len(hard_losses))*100:.1f} %)")
    print("-" * 100)

    # 1. Distribution des vraies pertes par Heure
    hour_losses = defaultdict(lambda: {"count": 0, "sum_loss": 0.0, "types": defaultdict(int)})
    for l in hard_losses:
        if l["dt_in"]:
            h = l["dt_in"].hour
            hour_losses[h]["count"] += 1
            hour_losses[h]["sum_loss"] += l["profit"]
            hour_losses[h]["types"][l["type"]] += 1

    print("\n📊 1. ANALYSE DES VRAIES PERTES PAR HEURE DE PRISE DE POSITION (Heure Serveur GMT+2/3) :")
    print(f"{'Heure':<8} {'Nombre de Pertes':<18} {'Perte Cumulée ($)':<20} {'Détail (Buy / Sell)'}")
    print("-" * 65)
    for h in sorted(hour_losses.keys()):
        hl = hour_losses[h]
        types_str = f"Buy: {hl['types']['buy']} | Sell: {hl['types']['sell']}"
        print(f"{h:02d}:00   {hl['count']:<18} {hl['sum_loss']:>+10.2f} $         {types_str}")

    # 2. Distribution par Jour de la Semaine
    day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    day_losses = defaultdict(lambda: {"count": 0, "sum_loss": 0.0})
    for l in hard_losses:
        if l["dt_in"]:
            w = l["dt_in"].weekday()
            day_losses[w]["count"] += 1
            day_losses[w]["sum_loss"] += l["profit"]

    print("\n📅 2. ANALYSE DES VRAIES PERTES PAR JOUR DE LA SEMAINE :")
    print(f"{'Jour':<12} {'Nombre de Pertes':<18} {'Perte Cumulée ($)':<20}")
    print("-" * 55)
    for w in sorted(day_losses.keys()):
        dl = day_losses[w]
        print(f"{day_names[w]:<12} {dl['count']:<18} {dl['sum_loss']:>+10.2f} $")

    # 3. Distribution par Durée de Rétention
    fast_losses = [l for l in hard_losses if l["duration_min"] <= 30]
    med_losses = [l for l in hard_losses if 30 < l["duration_min"] <= 120]
    slow_losses = [l for l in hard_losses if l["duration_min"] > 120]

    print("\n⏱️ 3. ANALYSE DE LA DURÉE DES POSITIONS AVANT D'ÊTRE STOPPÉES :")
    print(f"  • Flash Stop Loss (<= 30 min)  : {len(fast_losses)} trades (Perte: {sum(l['profit'] for l in fast_losses):.2f} $) -> Faux signaux de mèche / impulsions mortes-nées")
    print(f"  • Moyen Stop Loss (30 à 120 min): {len(med_losses)} trades (Perte: {sum(l['profit'] for l in med_losses):.2f} $) -> Retournements après consolidation")
    print(f"  • Long Stop Loss (> 120 min)   : {len(slow_losses)} trades (Perte: {sum(l['profit'] for l in slow_losses):.2f} $) -> Positions qui stagnent avant d'être sorties")

    print("\n📋 4. LISTE INTÉGRALE DES VRAIES PERTES (12 MOIS) :")
    header = f"{'#':<3} {'Type':<5} {'Heure Entrée':<17} {'Prix In':<10} {'Heure Sortie':<17} {'Prix Out':<10} {'Durée (min)':<12} {'Perte ($)'}"
    print(header)
    print("-" * len(header))
    for idx, l in enumerate(hard_losses, 1):
        print(f"{idx:<3} {l['type']:<5} {l['in_time']:<17} {l['in_price']:<10.2f} {l['out_time']:<17} {l['out_price']:<10.2f} {l['duration_min']:<12.0f} {l['profit']:>+8.2f} $")

if __name__ == "__main__":
    report = Path("/mnt/c/Users/samet/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/opt_rep_V35_Supreme_12M.htm")
    deep_autopsy(report)
