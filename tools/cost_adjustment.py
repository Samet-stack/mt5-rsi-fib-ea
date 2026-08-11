#!/usr/bin/env python3
"""Apply explicit, non-duplicative cost scenarios to parsed MT5 reports.

The input is the JSON emitted by ``tools/parse_mt5_report.py``.  MT5 deal
profit, commission, fee and swap are treated as native account-currency
amounts.  Bid/ask spread is already reflected in tester execution prices and
is therefore never charged again here.

When every trading deal contains ``position_id``, deals are grouped using that
identifier.  Older parser output does not expose it, so the documented
fallback uses FIFO lots by symbol and side.  FIFO cannot reconstruct scale-ins
as one broker position; each entry deal becomes a synthetic position.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, TextIO


_EPSILON = 1e-9


class CostAdjustmentError(ValueError):
    """Raised when parsed report data cannot be aggregated safely."""


def _finite_number(value: object, *, field_name: str, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise CostAdjustmentError(f"{field_name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CostAdjustmentError(f"{field_name} must be a finite number") from exc
    if not math.isfinite(number):
        raise CostAdjustmentError(f"{field_name} must be a finite number")
    return number


def _nonnegative(value: float, *, field_name: str) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise CostAdjustmentError(f"{field_name} must be finite and non-negative")
    return value


def _trade_deals(report: dict[str, object]) -> list[dict[str, object]]:
    raw_deals = report.get("deals")
    if not isinstance(raw_deals, list):
        raise CostAdjustmentError("report.deals must be a list")

    deals: list[dict[str, object]] = []
    for index, raw in enumerate(raw_deals):
        if not isinstance(raw, dict):
            raise CostAdjustmentError(f"report.deals[{index}] must be an object")
        direction = str(raw.get("direction", "")).strip().lower().replace(" ", "_")
        volume = _finite_number(
            raw.get("volume"), field_name=f"report.deals[{index}].volume"
        )
        if direction in {"in", "out"} and volume > _EPSILON:
            deal = dict(raw)
            deal["direction"] = direction
            deal["volume"] = volume
            deals.append(deal)
        elif (
            volume > _EPSILON
            and str(raw.get("type", "")).strip().lower() in {"buy", "sell"}
        ):
            raise CostAdjustmentError(
                f"unsupported trading deal direction at report.deals[{index}]: "
                f"{direction!r}"
            )
    return deals


def _deal_side(deal: dict[str, object], *, is_entry: bool) -> str:
    deal_type = str(deal.get("type", "")).strip().lower()
    if deal_type not in {"buy", "sell"}:
        raise CostAdjustmentError(f"unsupported trading deal type: {deal_type!r}")
    if is_entry:
        return "long" if deal_type == "buy" else "short"
    return "long" if deal_type == "sell" else "short"


def _deal_components(deal: dict[str, object]) -> dict[str, float]:
    return {
        name: _finite_number(deal.get(name), field_name=f"deal.{name}")
        for name in ("profit", "commission", "fee", "swap")
    }


@dataclass
class _Position:
    position_id: str
    symbol: str
    side: str
    first_time: str
    entry_volume: float = 0.0
    exit_volume: float = 0.0
    profit: float = 0.0
    commission: float = 0.0
    fee: float = 0.0
    swap: float = 0.0
    entry_deals: int = 0
    exit_deals: int = 0
    _open_volume: float = field(default=0.0, repr=False)

    def add(self, deal: dict[str, object], *, fraction: float = 1.0) -> None:
        direction = str(deal["direction"])
        volume = float(deal["volume"]) * fraction
        components = _deal_components(deal)
        if direction == "in":
            self.entry_volume += volume
            self._open_volume += volume
            self.entry_deals += 1
        elif direction == "out":
            self.exit_volume += volume
            self._open_volume -= volume
            self.exit_deals += 1
        else:  # pragma: no cover - filtered by _trade_deals
            raise CostAdjustmentError(f"unsupported deal direction: {direction!r}")
        for name, value in components.items():
            setattr(self, name, getattr(self, name) + value * fraction)


def _aggregate_by_position_id(deals: list[dict[str, object]]) -> list[_Position]:
    positions: dict[str, _Position] = {}
    for deal in deals:
        raw_id = deal.get("position_id")
        if raw_id is None or raw_id == "":
            raise CostAdjustmentError("mixed presence of position_id in trading deals")
        position_id = str(raw_id)
        symbol = str(deal.get("symbol", ""))
        direction = str(deal["direction"])
        side = _deal_side(deal, is_entry=(direction == "in"))
        if position_id not in positions:
            positions[position_id] = _Position(
                position_id=position_id,
                symbol=symbol,
                side=side,
                first_time=str(deal.get("time", "")),
            )
        position = positions[position_id]
        if position.symbol != symbol or position.side != side:
            raise CostAdjustmentError(
                f"position_id {position_id!r} mixes symbols or position sides"
            )
        position.add(deal)

    for position in positions.values():
        if position.exit_volume > position.entry_volume + _EPSILON:
            raise CostAdjustmentError(
                f"position_id {position.position_id!r} exits more volume than entered"
            )
    return sorted(positions.values(), key=lambda item: (item.first_time, item.position_id))


def _aggregate_fifo(deals: list[dict[str, object]]) -> list[_Position]:
    """Match exits to entry deals FIFO by symbol and side.

    Each entry deal creates one synthetic position.  An exit spanning several
    entries is allocated pro rata by consumed volume, including its native PnL
    and native cost components.
    """

    positions: list[_Position] = []
    queues: dict[tuple[str, str], deque[_Position]] = defaultdict(deque)
    sequence = 0

    for deal in deals:
        direction = str(deal["direction"])
        symbol = str(deal.get("symbol", ""))
        if not symbol:
            raise CostAdjustmentError("trading deal is missing symbol")
        side = _deal_side(deal, is_entry=(direction == "in"))
        key = (symbol, side)

        if direction == "in":
            sequence += 1
            position = _Position(
                position_id=f"fifo:{symbol}:{side}:{sequence}",
                symbol=symbol,
                side=side,
                first_time=str(deal.get("time", "")),
            )
            position.add(deal)
            positions.append(position)
            queues[key].append(position)
            continue

        remaining = float(deal["volume"])
        while remaining > _EPSILON:
            while queues[key] and queues[key][0]._open_volume <= _EPSILON:
                queues[key].popleft()
            if not queues[key]:
                raise CostAdjustmentError(
                    f"FIFO exit has no matching {side} entry for {symbol}"
                )
            position = queues[key][0]
            consumed = min(remaining, position._open_volume)
            fraction = consumed / float(deal["volume"])
            position.add(deal, fraction=fraction)
            remaining -= consumed
            if position._open_volume <= _EPSILON:
                queues[key].popleft()

    return positions


def aggregate_positions(report: dict[str, object]) -> tuple[str, list[_Position]]:
    """Aggregate trading deals, preferring explicit position identifiers."""

    deals = _trade_deals(report)
    if not deals:
        return "none", []
    has_position_id = [deal.get("position_id") not in {None, ""} for deal in deals]
    if all(has_position_id):
        return "position_id", _aggregate_by_position_id(deals)
    if any(has_position_id):
        raise CostAdjustmentError("position_id must be present on all or no trading deals")
    return "fifo", _aggregate_fifo(deals)


def _scenario(
    positions: list[_Position],
    *,
    round_turn_cost_per_lot: float,
    extra_slippage_cost_per_lot: float,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for position in positions:
        closed_volume = min(position.entry_volume, position.exit_volume)
        native_net = position.profit + position.commission + position.fee + position.swap
        native_commission_fee_cost = max(0.0, -(position.commission + position.fee))
        modeled_commission_fee_cost = round_turn_cost_per_lot * closed_volume
        additional_commission_fee = max(
            0.0, modeled_commission_fee_cost - native_commission_fee_cost
        )
        additional_slippage = extra_slippage_cost_per_lot * closed_volume
        additional_cost = additional_commission_fee + additional_slippage
        adjusted_net = native_net - additional_cost
        rows.append(
            {
                "additional_commission_fee": additional_commission_fee,
                "additional_cost": additional_cost,
                "additional_slippage": additional_slippage,
                "adjusted_net": adjusted_net,
                "closed_volume": closed_volume,
                "entry_deals": position.entry_deals,
                "entry_volume": position.entry_volume,
                "exit_deals": position.exit_deals,
                "exit_volume": position.exit_volume,
                "first_time": position.first_time,
                "native_commission": position.commission,
                "native_fee": position.fee,
                "native_net": native_net,
                "native_profit": position.profit,
                "native_swap": position.swap,
                "open_volume": max(0.0, position.entry_volume - position.exit_volume),
                "position_id": position.position_id,
                "side": position.side,
                "symbol": position.symbol,
            }
        )

    adjusted_values = [float(row["adjusted_net"]) for row in rows]
    gross_profit = sum(value for value in adjusted_values if value > 0.0)
    gross_loss = sum(value for value in adjusted_values if value < 0.0)
    adjusted_net = sum(adjusted_values)
    winners = sorted((value for value in adjusted_values if value > 0.0), reverse=True)
    best = winners[0] if winners else 0.0
    top_two = sum(winners[:2])
    winner_shares = [value / gross_profit for value in winners] if gross_profit else []

    return {
        "additional_cost": sum(float(row["additional_cost"]) for row in rows),
        "adjusted_gross_loss": gross_loss,
        "adjusted_gross_profit": gross_profit,
        "adjusted_net": adjusted_net,
        "concentration": {
            "best_position_profit": best if winners else None,
            "best_share_of_gross_profit": best / gross_profit if gross_profit else None,
            "best_share_of_net_profit": best / adjusted_net if adjusted_net > 0.0 else None,
            "hhi_of_winner_profits": sum(share * share for share in winner_shares),
            "net_without_best": adjusted_net - best if winners else adjusted_net,
            "net_without_two_best": adjusted_net - top_two,
            "top_two_share_of_gross_profit": (
                top_two / gross_profit if gross_profit else None
            ),
        },
        "losers": sum(value < 0.0 for value in adjusted_values),
        "native_commission": sum(position.commission for position in positions),
        "native_fee": sum(position.fee for position in positions),
        "native_profit": sum(position.profit for position in positions),
        "native_swap": sum(position.swap for position in positions),
        "positions": rows,
        "profit_factor": gross_profit / -gross_loss if gross_loss < 0.0 else None,
        "profit_factor_defined": gross_loss < 0.0,
        "round_turn_cost_per_lot": round_turn_cost_per_lot,
        "extra_slippage_cost_per_lot": extra_slippage_cost_per_lot,
        "total_closed_volume": sum(float(row["closed_volume"]) for row in rows),
        "total_entry_volume": sum(float(row["entry_volume"]) for row in rows),
        "trades": len(rows),
        "winners": len(winners),
    }


def adjust_report(
    report: dict[str, object],
    *,
    normal_round_turn_cost_per_lot: float = 0.0,
    stress_round_turn_cost_per_lot: float = 0.0,
    normal_extra_slippage_cost_per_lot: float = 0.0,
    stress_extra_slippage_cost_per_lot: float = 0.0,
) -> dict[str, object]:
    """Return deterministic normal/stress cost-adjusted report metrics."""

    for name, value in (
        ("normal_round_turn_cost_per_lot", normal_round_turn_cost_per_lot),
        ("stress_round_turn_cost_per_lot", stress_round_turn_cost_per_lot),
        ("normal_extra_slippage_cost_per_lot", normal_extra_slippage_cost_per_lot),
        ("stress_extra_slippage_cost_per_lot", stress_extra_slippage_cost_per_lot),
    ):
        _nonnegative(value, field_name=name)

    method, positions = aggregate_positions(report)
    normal = _scenario(
        positions,
        round_turn_cost_per_lot=normal_round_turn_cost_per_lot,
        extra_slippage_cost_per_lot=normal_extra_slippage_cost_per_lot,
    )
    stress = _scenario(
        positions,
        round_turn_cost_per_lot=stress_round_turn_cost_per_lot,
        extra_slippage_cost_per_lot=stress_extra_slippage_cost_per_lot,
    )
    native_positions_net = sum(
        position.profit + position.commission + position.fee + position.swap
        for position in positions
    )
    report_net = report.get("net_profit")
    parsed_report_net = (
        _finite_number(report_net, field_name="report.net_profit")
        if report_net is not None
        else None
    )
    return {
        "aggregation": {
            "method": method,
            "warning": (
                "FIFO fallback: each entry deal is a synthetic position; scale-ins "
                "cannot be reconstructed without position_id."
                if method == "fifo"
                else None
            ),
        },
        "cost_policy": {
            "native_commission_fee_swap_included": True,
            "spread_already_implicit_in_mt5_execution": True,
            "commission_fee_adjustment": (
                "max(0, scenario round-turn target - native commission/fee charge)"
            ),
            "swap_adjustment": "none; native swap is retained exactly once",
        },
        "expert": report.get("expert"),
        "native_positions_net": native_positions_net,
        "period": report.get("period"),
        "reconciliation_difference": (
            parsed_report_net - native_positions_net
            if parsed_report_net is not None
            else None
        ),
        "report": report.get("report"),
        "report_net_profit": parsed_report_net,
        "scenarios": {"normal": normal, "stress": stress},
        "symbol": report.get("symbol"),
    }


def _load_reports(stream: TextIO) -> list[dict[str, object]]:
    try:
        payload = json.load(stream)
    except json.JSONDecodeError as exc:
        raise CostAdjustmentError(f"invalid JSON: {exc}") from exc
    if isinstance(payload, dict):
        reports: Iterable[object] = [payload]
    elif isinstance(payload, list):
        reports = payload
    else:
        raise CostAdjustmentError("input JSON must be a report object or a list of reports")
    result: list[dict[str, object]] = []
    for index, report in enumerate(reports):
        if not isinstance(report, dict):
            raise CostAdjustmentError(f"report at index {index} must be an object")
        result.append(report)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply normal and stress costs to parse_mt5_report.py JSON"
    )
    parser.add_argument("input", help="parsed report JSON path, or '-' for stdin")
    parser.add_argument("--normal-round-turn-cost-per-lot", type=float, default=0.0)
    parser.add_argument("--stress-round-turn-cost-per-lot", type=float)
    parser.add_argument("--normal-extra-slippage-cost-per-lot", type=float, default=0.0)
    parser.add_argument("--stress-extra-slippage-cost-per-lot", type=float)
    return parser


def _clean_json_numbers(value: object) -> object:
    """Remove floating-point display noise without changing JSON structure."""

    if isinstance(value, float):
        rounded = round(value, 12)
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, list):
        return [_clean_json_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_json_numbers(item) for key, item in value.items()}
    return value


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.input == "-":
            reports = _load_reports(sys.stdin)
        else:
            with Path(args.input).open("r", encoding="utf-8") as stream:
                reports = _load_reports(stream)

        stress_cost = (
            args.normal_round_turn_cost_per_lot
            if args.stress_round_turn_cost_per_lot is None
            else args.stress_round_turn_cost_per_lot
        )
        stress_slippage = (
            args.normal_extra_slippage_cost_per_lot
            if args.stress_extra_slippage_cost_per_lot is None
            else args.stress_extra_slippage_cost_per_lot
        )
        adjusted = [
            adjust_report(
                report,
                normal_round_turn_cost_per_lot=args.normal_round_turn_cost_per_lot,
                stress_round_turn_cost_per_lot=stress_cost,
                normal_extra_slippage_cost_per_lot=(
                    args.normal_extra_slippage_cost_per_lot
                ),
                stress_extra_slippage_cost_per_lot=stress_slippage,
            )
            for report in reports
        ]
    except (CostAdjustmentError, OSError) as exc:
        print(f"cost_adjustment: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            _clean_json_numbers(adjusted),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
