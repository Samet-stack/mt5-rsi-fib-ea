#!/usr/bin/env python3
"""Static fail-closed contracts for the Windows MT5 backtest runner."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (ROOT / "tools/run_mt5_backtest.ps1").read_text(encoding="utf-8")


class TestMT5RunnerSource(unittest.TestCase):
    def test_runner_requests_real_ticks_and_rejects_synthetic_history(self):
        self.assertIn("Model=4", RUNNER)
        self.assertIn("MinRealTicksPct = 99.0", RUNNER)
        self.assertIn("real-tick quality", RUNNER)
        self.assertIn("$realTicksPct -lt $MinRealTicksPct", RUNNER)
        self.assertIn("RealTicksPct = $realTicksPct", RUNNER)

    def test_runner_remains_tester_only_and_local(self):
        self.assertIn("AllowLiveTrading=0", RUNNER)
        self.assertIn("AllowDllImport=0", RUNNER)
        self.assertIn("UseLocal=1", RUNNER)
        self.assertIn("UseRemote=0", RUNNER)
        self.assertIn("UseCloud=0", RUNNER)


if __name__ == "__main__":
    unittest.main()
