import unittest

from tools.portfolio_evaluator import (
    PortfolioEvaluationError,
    evaluate_reports,
    extract_window,
    parse_symbol_values,
)


def _report(symbol, profits, volumes=None, *, ticks=100.0, period=None):
    volumes = volumes or [1.0] * len(profits)
    deals = []
    balance = 3000.0
    for index, (profit, volume) in enumerate(zip(profits, volumes), start=1):
        deals.append(
            {
                "commission": 0.0,
                "direction": "in",
                "fee": 0.0,
                "profit": 0.0,
                "swap": 0.0,
                "symbol": symbol,
                "time": f"2026.07.{index:02d} 10:00:00",
                "type": "buy",
                "volume": volume,
            }
        )
        balance += profit
        deals.append(
            {
                "commission": 0.0,
                "direction": "out",
                "fee": 0.0,
                "profit": profit,
                "swap": 0.0,
                "symbol": symbol,
                "time": f"2026.07.{index:02d} 11:00:00",
                "type": "sell",
                "volume": volume,
            }
        )
    return {
        "currency": "USD",
        "deals": deals,
        "deposit": 3000.0,
        "equity_drawdown_max_pct": 1.0,
        "expert": "RSIFibRetracementEA",
        "net_profit": sum(profits),
        "period": period or "M15 (2026.07.01 - 2026.07.31)",
        "real_ticks_pct": ticks,
        "report": f"{symbol}.htm",
        "symbol": symbol,
    }


class TestPortfolioEvaluator(unittest.TestCase):
    def test_symbol_cost_parser_is_explicit_and_rejects_duplicates(self):
        self.assertEqual(parse_symbol_values(["xauusd=7.5"], "--cost"), {"XAUUSD": 7.5})
        with self.assertRaises(PortfolioEvaluationError):
            parse_symbol_values(["XAUUSD=7", "xauusd=8"], "--cost")
        with self.assertRaises(PortfolioEvaluationError):
            parse_symbol_values(["XAUUSD"], "--cost")

    def test_extract_window_requires_two_exact_dates(self):
        self.assertEqual(
            extract_window("M15 (2026.07.01 - 2026.07.31)"),
            ("2026.07.01", "2026.07.31"),
        )
        with self.assertRaises(PortfolioEvaluationError):
            extract_window("M15")

    def test_missing_symbol_cost_fails_closed(self):
        with self.assertRaisesRegex(PortfolioEvaluationError, "missing explicit"):
            evaluate_reports([_report("XAUUSD", [10.0, -2.0])], normal_costs={})

    def test_low_real_tick_quality_and_mismatched_windows_fail_closed(self):
        with self.assertRaisesRegex(PortfolioEvaluationError, "real tick quality"):
            evaluate_reports(
                [_report("XAUUSD", [10.0], ticks=98.9)],
                normal_costs={"XAUUSD": 1.0},
            )
        with self.assertRaisesRegex(PortfolioEvaluationError, "windows differ"):
            evaluate_reports(
                [
                    _report("XAUUSD", [10.0]),
                    _report(
                        "USTEC",
                        [10.0],
                        period="M15 (2026.06.01 - 2026.06.30)",
                    ),
                ],
                normal_costs={"XAUUSD": 1.0, "USTEC": 1.0},
            )

    def test_costs_are_symbol_specific_and_gate_rejects_concentration(self):
        result = evaluate_reports(
            [
                _report("XAUUSD", [20.0, -2.0], [1.0, 1.0]),
                _report("USTEC", [4.0, -1.0], [2.0, 2.0]),
            ],
            normal_costs={"XAUUSD": 1.0, "USTEC": 0.5},
            stress_costs={"XAUUSD": 2.0, "USTEC": 1.0},
            min_trades_per_30d=1.0,
            max_trades_per_30d=20.0,
            min_normal_profit_factor=1.0,
            min_stress_profit_factor=1.0,
        )
        self.assertEqual(result["normal"]["trades"], 4)
        self.assertAlmostEqual(result["normal"]["adjusted_net"], 17.0)
        self.assertFalse(result["candidate_gate"]["passed"])
        self.assertFalse(
            result["candidate_gate"]["checks"]["best_share_of_gross_profit"]
        )
        self.assertIn("not a synchronized", result["limitations"][0])

    def test_unused_cost_entry_is_rejected(self):
        with self.assertRaisesRegex(PortfolioEvaluationError, "absent symbols"):
            evaluate_reports(
                [_report("XAUUSD", [10.0, -1.0])],
                normal_costs={"XAUUSD": 1.0, "USTEC": 1.0},
            )


if __name__ == "__main__":
    unittest.main()
