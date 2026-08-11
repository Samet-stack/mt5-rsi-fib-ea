#!/usr/bin/env python3
"""Print a compact, report-derived MT5 backtest summary.

No performance number is embedded in this script. The report path is supplied
by the caller so the tool remains portable and auditable in a public checkout.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.parse_mt5_report import parse_report


def summarize(report_path: Path) -> None:
    if not report_path.is_file():
        raise FileNotFoundError(f"Report not found: {report_path}")

    data = parse_report(report_path)
    print(f"=== MT5 REPORT SUMMARY: {report_path.name} ===")
    for label, key in (
        ("Symbol", "symbol"),
        ("Period", "period"),
        ("Net profit", "net_profit"),
        ("Profit factor", "profit_factor"),
        ("Expected payoff", "expected_payoff"),
        ("Trades", "trades"),
        ("Winners", "winners"),
        ("Max equity drawdown %", "equity_drawdown_max_pct"),
    ):
        print(f"{label}: {data.get(key, 'unavailable')}")
    print("These are historical tester outputs, not a forecast or profit guarantee.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to an MT5 HTML report")
    args = parser.parse_args()
    summarize(args.report)


if __name__ == "__main__":
    main()
