#!/usr/bin/env python3
"""Static contracts for the tester-only, non-trading MT5 symbol probe."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT_ROOT / "MQL5" / "Experts" / "RSIFibSymbolProbeEA.mq5").read_text(
    encoding="utf-8"
)
RUNNER = (PROJECT_ROOT / "tools" / "run_mt5_symbol_probe.ps1").read_text(
    encoding="utf-8"
)


class TestSymbolProbeSource(unittest.TestCase):
    def test_probe_is_tester_only_and_contains_no_trade_api(self):
        self.assertIn("MQLInfoInteger(MQL_TESTER)", SOURCE)
        self.assertIn("orders_sent\", \"0\"", SOURCE)
        for forbidden in (
            "CTrade",
            "OrderSend(",
            ".Buy(",
            ".Sell(",
            "BuyLimit(",
            "SellLimit(",
            "OrderDelete(",
            "PositionModify(",
            "PositionClose(",
        ):
            self.assertNotIn(forbidden, SOURCE)

    def test_probe_never_reads_personal_account_identifiers(self):
        for forbidden in ("ACCOUNT_LOGIN", "ACCOUNT_NAME"):
            self.assertNotIn(forbidden, SOURCE)
        self.assertIn("ACCOUNT_SERVER", SOURCE)
        self.assertIn("ACCOUNT_COMPANY", SOURCE)

    def test_probe_captures_sizing_and_execution_properties(self):
        for token in (
            "SYMBOL_TRADE_CALC_MODE",
            "SYMBOL_TRADE_EXEMODE",
            "SYMBOL_TRADE_TICK_SIZE",
            "SYMBOL_TRADE_TICK_VALUE_LOSS",
            "SYMBOL_TRADE_CONTRACT_SIZE",
            "SYMBOL_VOLUME_MIN",
            "SYMBOL_VOLUME_STEP",
            "SYMBOL_TRADE_STOPS_LEVEL",
            "SYMBOL_TRADE_FREEZE_LEVEL",
            "SYMBOL_START_TIME",
            "SYMBOL_EXPIRATION_TIME",
            "OrderCalcMargin",
            "OrderCalcProfit",
            "SymbolInfoSessionTrade",
        ):
            self.assertIn(token, SOURCE)

    def test_runner_disables_all_trading_and_remote_agents(self):
        for setting in (
            "Enabled=0",
            "AllowLiveTrading=0",
            "AllowDllImport=0",
            "UseLocal=1",
            "UseRemote=0",
            "UseCloud=0",
            "Optimization=0",
        ):
            self.assertIn(setting, RUNNER)


if __name__ == "__main__":
    unittest.main()
