#!/usr/bin/env python3
"""Tests for deterministic report diagnostics and uncertainty helpers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from tools.diagnostic_analyzer import (
    DiagnosticError,
    analyze_report,
    moving_block_bootstrap_mean_ci,
    reconstruct_trades,
    wilson_interval,
)
from tools.parse_mt5_report import parse_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "artifacts" / "validation-2026-08-04"


def probe() -> dict[str, object]:
    return {
        "schema": "rsifib-mt5-symbol-probe/v1",
        "tester_only": True,
        "orders_sent": 0,
        "symbol": "XAUUSD",
        "broker_company": "MetaQuotes Ltd.",
        "server": "MetaQuotes-Demo",
        "account_currency": "USD",
        "terminal_build": 6090,
        "account_balance": 3000.0,
        "account_leverage": 100,
        "contract_size": 100.0,
        "tick_size": 0.01,
        "tick_value": 0.1,
        "volume_min": 0.01,
        "min_volume_one_tick_buy_pnl": -0.01,
        "min_volume_one_tick_sell_pnl": -0.01,
    }


class TestDiagnosticMath(unittest.TestCase):
    def test_risk_uses_order_calc_profit_probe_not_contract_size_shortcut(self):
        report = {
            "symbol": "MGC",
            "broker": "Example Futures",
            "server": "Example-Demo",
            "currency": "USD",
            "terminal_build": 6090,
            "deposit": 3000.0,
            "leverage": "1:100",
            "orders": [
                {
                    "order": 1,
                    "type": "buy limit",
                    "price": 2500.0,
                    "sl": 2499.7,
                    "tp": 2501.0,
                }
            ],
            "deals": [
                {
                    "order": 1,
                    "type": "buy",
                    "direction": "in",
                    "time": "2026.01.01 10:00:00",
                    "price": 2500.0,
                    "volume": 1.0,
                    "commission": 0.0,
                    "swap": 0.0,
                    "profit": 0.0,
                },
                {
                    "order": 2,
                    "type": "sell",
                    "direction": "out",
                    "time": "2026.01.01 10:01:00",
                    "price": 2499.7,
                    "volume": 1.0,
                    "commission": 0.0,
                    "swap": 0.0,
                    "profit": -3.0,
                    "comment": "sl 2499.7",
                },
            ],
        }
        symbol_probe = {
            "symbol": "MGC",
            "broker_company": "Example Futures",
            "server": "Example-Demo",
            "account_currency": "USD",
            "terminal_build": 6090,
            "account_balance": 3000.0,
            "account_leverage": 100,
            "contract_size": 999.0,
            "tick_size": 0.1,
            "volume_min": 1.0,
            "min_volume_one_tick_buy_pnl": -1.0,
            "min_volume_one_tick_sell_pnl": -1.0,
        }
        trade = reconstruct_trades(report, symbol_probe)[0]
        self.assertAlmostEqual(trade["initial_risk_money"], 3.0)
        self.assertEqual(trade["risk_valuation"], "order_calc_profit_probe")

    def test_report_probe_broker_mismatch_is_rejected(self):
        report = {
            "symbol": "XAUUSD",
            "broker": "Wrong Broker",
            "server": "MetaQuotes-Demo",
            "currency": "USD",
            "terminal_build": 6090,
            "deposit": 3000.0,
            "leverage": "1:100",
            "orders": [],
            "deals": [],
        }
        with self.assertRaisesRegex(DiagnosticError, "broker mismatch"):
            reconstruct_trades(report, probe())

    def test_report_totals_cannot_be_overridden_by_reconstructed_profit(self):
        synthetic_report = {
            "report": "synthetic",
            "symbol": "XAUUSD",
            "broker": "MetaQuotes Ltd.",
            "server": "MetaQuotes-Demo",
            "currency": "USD",
            "terminal_build": 6090,
            "deposit": 3000.0,
            "leverage": "1:100",
            "period": "M15 (2026.01.01 - 2026.01.02)",
            "history_quality": "100% real ticks",
            "real_ticks_pct": 100.0,
            "profit_factor": 2.0,
            "net_profit": -100.0,
            "trades": 1,
            "winners": 1,
            "losers": 0,
            "orders": [
                {
                    "order": 1,
                    "type": "buy limit",
                    "price": 2500.0,
                    "sl": 2499.7,
                    "tp": 2501.0,
                    "state": "filled",
                }
            ],
            "deals": [
                {
                    "order": 1,
                    "type": "buy",
                    "direction": "in",
                    "time": "2026.01.01 10:00:00",
                    "price": 2500.0,
                    "volume": 0.01,
                    "commission": -0.01,
                    "fee": -0.01,
                    "swap": 0.0,
                    "profit": 0.0,
                },
                {
                    "order": 2,
                    "type": "sell",
                    "direction": "out",
                    "time": "2026.01.01 10:01:00",
                    "price": 2500.3,
                    "volume": 0.01,
                    "commission": -0.01,
                    "fee": -0.01,
                    "swap": 0.0,
                    "profit": 0.30,
                    "comment": "tp 2500.3",
                },
            ],
        }
        result = analyze_report(synthetic_report, probe())
        codes = {finding["code"] for finding in result["findings"]}
        self.assertEqual(result["verdict"], "INVALID_TECHNICAL")
        self.assertIn("RECONSTRUCTED_NET_PROFIT_MISMATCH", codes)

    def test_minimum_trade_floor_cannot_be_lowered_after_results(self):
        with self.assertRaisesRegex(ValueError, "fail-closed floor"):
            analyze_report({}, {}, min_trades=1)

    def test_wilson_interval_known_examples(self):
        low, high = wilson_interval(1, 48)
        self.assertAlmostEqual(low, 0.003683, places=5)
        self.assertAlmostEqual(high, 0.108992, places=5)
        low, high = wilson_interval(3, 52)
        self.assertLess(low, 0.0411)
        self.assertGreater(high, 0.10)

    def test_block_bootstrap_is_deterministic(self):
        values = [0.0, -1.0, 0.0, 2.0, 0.0, -0.5, 0.0]
        first = moving_block_bootstrap_mean_ci(values, replications=500, seed=7)
        second = moving_block_bootstrap_mean_ci(values, replications=500, seed=7)
        self.assertEqual(first, second)
        self.assertLess(first[0], first[1])


class TestLegacyReportDiagnostics(unittest.TestCase):
    def test_direct_cli_execution_from_project_root(self):
        completed = subprocess.run(
            [
                sys.executable,
                "tools/diagnostic_analyzer.py",
                str(REPORT_DIR / "RSIFibEA_OOS_202605_202607_xau_stop039_be0_010.htm"),
                "--probe",
                str(
                    PROJECT_ROOT
                    / "artifacts"
                    / "symbol-probe-2026-08-05"
                    / "XAUUSD_MetaQuotes-Demo.json"
                ),
                "--summary-only",
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["summary"]["trades"], 48)

    def test_rejected_oos_jackpot_distribution(self):
        report = parse_report(
            REPORT_DIR / "RSIFibEA_OOS_202605_202607_xau_stop039_be0_010.htm"
        )
        result = analyze_report(report, probe())
        summary = result["summary"]

        self.assertEqual(result["verdict"], "INVALID_TECHNICAL")
        self.assertEqual(summary["trades"], 48)
        self.assertEqual(summary["full_tp"], 1)
        self.assertEqual(summary["exits_within_2_minutes"], 30)
        self.assertEqual(summary["exits_under_5_minutes"], 37)
        self.assertAlmostEqual(summary["net_profit_reconstructed"], -21.87, places=2)
        self.assertGreater(summary["largest_positive_share"], 0.99)
        self.assertFalse(summary["mfe_mae_available"])
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("COMMISSION_UNVERIFIED_ZERO", codes)
        self.assertIn("DEAL_FEE_NOT_EXPORTED", codes)
        self.assertIn("INSUFFICIENT_SAMPLE_SIZE", codes)
        self.assertIn("NEGATIVE_EXPECTANCY", codes)
        self.assertIn("TP_PROBABILITY_LOWER_BOUND_BELOW_BREAK_EVEN", codes)
        self.assertIn("SYMBOL_TICK_VALUE_DISAGREES_WITH_ORDER_CALC_PROFIT", codes)

    def test_is_result_is_inconclusive_after_concentration_and_uncertainty(self):
        report = parse_report(
            REPORT_DIR / "RSIFibEA_IS_202602_202605_RSIFibEA_xau_stop039_be0_010.htm"
        )
        result = analyze_report(report, probe())
        summary = result["summary"]

        self.assertEqual(summary["trades"], 52)
        self.assertEqual(summary["full_tp"], 3)
        self.assertGreater(summary["largest_positive_share"], 0.45)
        self.assertLess(summary["net_without_largest_positive"], 0.0)


if __name__ == "__main__":
    unittest.main()
