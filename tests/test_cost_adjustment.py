from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from cost_adjustment import CostAdjustmentError, adjust_report  # noqa: E402


def _deal(
    *,
    time: str,
    deal_type: str,
    direction: str,
    volume: float,
    profit: float = 0.0,
    commission: float = 0.0,
    fee: float = 0.0,
    swap: float = 0.0,
    position_id: int | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "time": time,
        "symbol": "XAUUSD",
        "type": deal_type,
        "direction": direction,
        "volume": volume,
        "profit": profit,
        "commission": commission,
        "fee": fee,
        "swap": swap,
    }
    if position_id is not None:
        result["position_id"] = position_id
    return result


class CostAdjustmentTests(unittest.TestCase):
    def test_position_id_partial_exits_and_native_costs_are_not_doubled(self) -> None:
        report = {
            "report": "fixture.htm",
            "expert": "EA",
            "symbol": "XAUUSD",
            "period": "M15",
            "net_profit": 38.5,
            "deals": [
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in",
                    volume=1.0,
                    commission=-2.0,
                    position_id=101,
                ),
                _deal(
                    time="2026.01.01 11:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=0.4,
                    profit=40.0,
                    commission=-1.0,
                    swap=-2.0,
                    position_id=101,
                ),
                _deal(
                    time="2026.01.01 12:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=0.6,
                    profit=30.0,
                    commission=-2.0,
                    fee=-1.0,
                    position_id=101,
                ),
                _deal(
                    time="2026.01.02 10:00:00",
                    deal_type="sell",
                    direction="in",
                    volume=0.5,
                    commission=-1.5,
                    position_id=102,
                ),
                _deal(
                    time="2026.01.02 11:00:00",
                    deal_type="buy",
                    direction="out",
                    volume=0.5,
                    profit=-20.0,
                    commission=-2.0,
                    position_id=102,
                ),
            ],
        }

        result = adjust_report(
            report,
            normal_round_turn_cost_per_lot=7.0,
            stress_round_turn_cost_per_lot=10.0,
            normal_extra_slippage_cost_per_lot=2.0,
            stress_extra_slippage_cost_per_lot=4.0,
        )

        self.assertEqual(result["aggregation"]["method"], "position_id")
        self.assertAlmostEqual(result["native_positions_net"], 38.5)
        self.assertAlmostEqual(result["reconciliation_difference"], 0.0)

        normal = result["scenarios"]["normal"]
        first, second = normal["positions"]
        self.assertEqual(first["entry_deals"], 1)
        self.assertEqual(first["exit_deals"], 2)
        self.assertAlmostEqual(first["entry_volume"], 1.0)
        self.assertAlmostEqual(first["closed_volume"], 1.0)
        self.assertAlmostEqual(first["native_net"], 62.0)
        self.assertAlmostEqual(first["additional_commission_fee"], 1.0)
        self.assertAlmostEqual(first["additional_slippage"], 2.0)
        self.assertAlmostEqual(first["adjusted_net"], 59.0)
        self.assertAlmostEqual(second["native_net"], -23.5)
        self.assertAlmostEqual(second["additional_commission_fee"], 0.0)
        self.assertAlmostEqual(second["adjusted_net"], -24.5)
        self.assertAlmostEqual(normal["adjusted_net"], 34.5)
        self.assertAlmostEqual(normal["profit_factor"], 59.0 / 24.5)
        self.assertAlmostEqual(normal["concentration"]["net_without_best"], -24.5)

        stress = result["scenarios"]["stress"]
        self.assertAlmostEqual(stress["positions"][0]["additional_cost"], 8.0)
        self.assertAlmostEqual(stress["positions"][0]["adjusted_net"], 54.0)

    def test_fifo_fallback_aggregates_partial_exits(self) -> None:
        report = {
            "net_profit": 11.0,
            "deals": [
                {"type": "balance", "direction": "", "profit": 3000.0},
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in",
                    volume=1.0,
                    commission=-1.0,
                ),
                _deal(
                    time="2026.01.01 11:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=0.4,
                    profit=4.0,
                    commission=-0.4,
                ),
                _deal(
                    time="2026.01.01 12:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=0.6,
                    profit=9.0,
                    commission=-0.6,
                ),
            ],
        }

        result = adjust_report(
            report,
            normal_round_turn_cost_per_lot=2.0,
            stress_round_turn_cost_per_lot=2.0,
        )
        normal = result["scenarios"]["normal"]

        self.assertEqual(result["aggregation"]["method"], "fifo")
        self.assertIn("scale-ins", result["aggregation"]["warning"])
        self.assertEqual(normal["trades"], 1)
        position = normal["positions"][0]
        self.assertEqual(position["position_id"], "fifo:XAUUSD:long:1")
        self.assertEqual(position["exit_deals"], 2)
        self.assertAlmostEqual(position["entry_volume"], 1.0)
        self.assertAlmostEqual(position["exit_volume"], 1.0)
        self.assertAlmostEqual(position["native_net"], 11.0)
        self.assertAlmostEqual(position["additional_commission_fee"], 0.0)
        self.assertAlmostEqual(position["adjusted_net"], 11.0)

    def test_fifo_allocates_one_exit_across_two_entries(self) -> None:
        report = {
            "deals": [
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in",
                    volume=0.4,
                ),
                _deal(
                    time="2026.01.01 10:05:00",
                    deal_type="buy",
                    direction="in",
                    volume=0.6,
                ),
                _deal(
                    time="2026.01.01 11:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=1.0,
                    profit=10.0,
                    commission=-2.0,
                ),
            ]
        }

        result = adjust_report(report)
        positions = result["scenarios"]["normal"]["positions"]
        self.assertEqual(len(positions), 2)
        self.assertAlmostEqual(positions[0]["native_profit"], 4.0)
        self.assertAlmostEqual(positions[0]["native_commission"], -0.8)
        self.assertAlmostEqual(positions[1]["native_profit"], 6.0)
        self.assertAlmostEqual(positions[1]["native_commission"], -1.2)

    def test_mixed_position_ids_fail_closed(self) -> None:
        report = {
            "deals": [
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in",
                    volume=1.0,
                    position_id=1,
                ),
                _deal(
                    time="2026.01.01 11:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=1.0,
                    profit=1.0,
                ),
            ]
        }
        with self.assertRaisesRegex(CostAdjustmentError, "all or no"):
            adjust_report(report)

    def test_reversal_direction_fails_closed_instead_of_losing_a_deal(self) -> None:
        report = {
            "deals": [
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in/out",
                    volume=1.0,
                )
            ]
        }
        with self.assertRaisesRegex(CostAdjustmentError, "unsupported.*direction"):
            adjust_report(report)

    def test_cli_json_is_deterministic_and_stress_defaults_to_normal(self) -> None:
        report = {
            "net_profit": 10.0,
            "deals": [
                _deal(
                    time="2026.01.01 10:00:00",
                    deal_type="buy",
                    direction="in",
                    volume=1.0,
                ),
                _deal(
                    time="2026.01.01 11:00:00",
                    deal_type="sell",
                    direction="out",
                    volume=1.0,
                    profit=10.0,
                ),
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "report.json"
            path.write_text(json.dumps([report]), encoding="utf-8")
            command = [
                sys.executable,
                str(TOOLS / "cost_adjustment.py"),
                str(path),
                "--normal-round-turn-cost-per-lot",
                "7",
                "--normal-extra-slippage-cost-per-lot",
                "2",
            ]
            first = subprocess.run(command, check=True, text=True, capture_output=True)
            second = subprocess.run(command, check=True, text=True, capture_output=True)

        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload[0]["scenarios"]["normal"], payload[0]["scenarios"]["stress"])
        self.assertAlmostEqual(payload[0]["scenarios"]["normal"]["adjusted_net"], 1.0)


if __name__ == "__main__":
    unittest.main()
