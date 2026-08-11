#!/usr/bin/env python3
"""Static contracts for the tester-only read-only symbol catalog."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "MQL5/Experts/RSIFibSymbolCatalogEA.mq5").read_text(
    encoding="utf-8")
RUNNER = (ROOT / "tools/run_mt5_symbol_catalog.ps1").read_text(
    encoding="utf-8")


class TestSymbolCatalogSource(unittest.TestCase):
    def test_catalog_is_tester_only_and_contains_no_trading_api(self):
        self.assertIn("MQLInfoInteger(MQL_TESTER)", SOURCE)
        self.assertIn("orders_sent", SOURCE)
        self.assertIn("SymbolsTotal(false)", SOURCE)
        self.assertIn("SymbolName(i, false)", SOURCE)
        self.assertNotIn("SymbolSelect", SOURCE)
        for forbidden in (
            "CTrade", "OrderSend", "Buy(", "Sell(", "BuyLimit",
            "SellLimit", "PositionClose", "OrderDelete",
        ):
            self.assertNotIn(forbidden, SOURCE)

    def test_runner_disables_live_trading_and_validates_output(self):
        self.assertIn("AllowLiveTrading=0", RUNNER)
        self.assertIn("UseRemote=0", RUNNER)
        self.assertIn("UseCloud=0", RUNNER)
        self.assertIn("orders_sent", RUNNER)
        self.assertIn("rsifib-mt5-symbol-catalog/v1", RUNNER)


if __name__ == "__main__":
    unittest.main()
