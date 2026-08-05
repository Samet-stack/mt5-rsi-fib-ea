#!/usr/bin/env python3
"""Tests for the dependency-free MT5 report parser."""

from pathlib import Path
import tempfile
import unittest

from tools.parse_mt5_report import _parse_deal_rows, parse_report


class TestMT5ReportParser(unittest.TestCase):
    def test_deal_parser_is_header_driven_and_preserves_fee(self):
        rows = [
            ["Deals"],
            [
                "Time",
                "Deal",
                "Symbol",
                "Type",
                "Direction",
                "Volume",
                "Price",
                "Order",
                "Commission",
                "Fee",
                "Swap",
                "Profit",
                "Balance",
                "Comment",
            ],
            [
                "2026.01.01 00:00:01",
                "2",
                "MGC",
                "buy",
                "in",
                "1",
                "2500.1",
                "1",
                "-0.25",
                "-0.10",
                "0.00",
                "0.00",
                "2999.65",
                "entry",
            ],
        ]
        deal = _parse_deal_rows(rows)[0]
        self.assertAlmostEqual(deal["commission"], -0.25)
        self.assertAlmostEqual(deal["fee"], -0.10)

    def test_parses_utf16_french_report_metrics(self):
        labels = {
            "Expert:": "RSIFibRetracementEA",
            "Symbole:": "XAUUSD",
            "Période:": "M15 (2026.02.01 - 2026.05.01)",
            "Dépôt initial:": "3 000.00",
            "Levier:": "1:100",
            "Qualité de l'Historique:": "100% ticks réel",
            "Barres:": "8 000",
            "Tiques:": "12 345 678",
            "Profit Total Net:": "42.50",
            "Profit brut:": "100.00",
            "Perte brut:": "-57.50",
            "Fond Drawdown Maximal:": "25.00 (0.83%)",
            "Facteur de profit:": "1.74",
            "Remboursement attendu:": "0.85",
            "Ratio de Sharpe:": "1.20",
            "Résultat de la fonction OnTester:": "0.52",
            "Nb trades:": "50",
            "Positions gagnantes (% du total):": "5 (10.00%)",
            "Positions perdantes (% du total):": "45 (90.00%)",
        }
        rows = "".join(
            f"<tr><td>{label}</td><td><b>{value}</b></td></tr>"
            for label, value in labels.items()
        )
        html = f"<html><body><table>{rows}</table></body></html>"

        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.htm"
            report.write_text(html, encoding="utf-16")
            result = parse_report(report)

        self.assertEqual(result["history_quality"], "100% ticks réel")
        self.assertEqual(result["real_ticks_pct"], 100.0)
        self.assertEqual(result["ticks"], 12_345_678)
        self.assertEqual(result["trades"], 50)
        self.assertEqual(result["winners"], 5)
        self.assertEqual(result["losers"], 45)
        self.assertAlmostEqual(result["net_profit"], 42.50)
        self.assertAlmostEqual(result["equity_drawdown_max_pct"], 0.83)
        self.assertAlmostEqual(result["profit_factor"], 1.74)

    def test_missing_same_row_value_is_not_taken_from_next_row(self):
        rows = """
        <tr><td>Expert:</td><td></td></tr>
        <tr><td>Symbole:</td><td>XAUUSD</td></tr>
        """
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "missing.htm"
            report.write_text(f"<html><table>{rows}</table></html>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "value missing after label: Expert"):
                parse_report(report)

    def test_parses_real_orders_deals_inputs_and_server(self):
        project_root = Path(__file__).resolve().parents[1]
        report = (
            project_root
            / "artifacts"
            / "validation-2026-08-04"
            / "RSIFibEA_OOS_202605_202607_xau_stop039_be0_010.htm"
        )
        result = parse_report(report)

        self.assertEqual(result["server_build"], "MetaQuotes-Demo (Build 6090)")
        self.assertEqual(result["server"], "MetaQuotes-Demo")
        self.assertEqual(result["terminal_build"], 6090)
        self.assertEqual(result["broker"], "MetaQuotes Ltd.")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["inputs"]["InpStopRatio"], "-0.39")
        self.assertEqual(result["inputs"]["InpUseBreakEven"], "true")
        self.assertEqual(len(result["orders"]), 107)
        self.assertEqual(len(result["deals"]), 97)
        self.assertEqual(result["orders"][0]["type"], "buy limit")
        self.assertEqual(result["deals"][1]["direction"], "in")
        self.assertEqual(result["deals"][2]["direction"], "out")
        self.assertIsNone(result["deals"][2]["fee"])


if __name__ == "__main__":
    unittest.main()
