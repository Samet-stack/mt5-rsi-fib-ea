#!/usr/bin/env python3
"""Deterministic diagnostics for MT5 RSI/Fib reports.

This tool is intentionally a rejection tool, not an optimizer.  It reconstructs
closed trades from the Orders/Deals tables, measures concentration and timing,
and reports uncertainty.  Per-trade MFE/MAE require the V3 shadow ledger and are
therefore explicitly marked unavailable for legacy HTML reports.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import random
import re
from statistics import mean, median
import sys
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.parse_mt5_report import parse_report


SCHEMA = "rsifib-report-diagnostic/v1"
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"
MINIMUM_TRADES_FLOOR = 100


class DiagnosticError(RuntimeError):
    pass


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson interval requires 0 <= successes <= total and total > 0")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    ) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot compute a percentile of an empty sample")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def moving_block_bootstrap_mean_ci(
    values: list[float],
    block_length: int = 5,
    replications: int = 10_000,
    seed: int = 20260805,
) -> tuple[float, float]:
    if not values:
        raise ValueError("Bootstrap requires at least one observation")
    if block_length < 1 or replications < 100:
        raise ValueError("Invalid block bootstrap configuration")
    n = len(values)
    block_length = min(block_length, n)
    random_generator = random.Random(seed)
    samples: list[float] = []
    for _ in range(replications):
        synthetic: list[float] = []
        while len(synthetic) < n:
            start = random_generator.randrange(0, n - block_length + 1)
            synthetic.extend(values[start : start + block_length])
        samples.append(mean(synthetic[:n]))
    return percentile(samples, 0.025), percentile(samples, 0.975)


def _load_probe(path: Path) -> dict[str, Any]:
    try:
        probe = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"Cannot read symbol probe {path}: {exc}") from exc
    if not isinstance(probe, dict):
        raise DiagnosticError("Symbol probe must contain a JSON object")
    if probe.get("schema") != "rsifib-mt5-symbol-probe/v1":
        raise DiagnosticError("Unsupported symbol probe schema")
    if probe.get("tester_only") is not True or probe.get("orders_sent") != 0:
        raise DiagnosticError("Unsafe or invalid symbol probe")
    return probe


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except ValueError as exc:
        raise DiagnosticError(f"Invalid MT5 timestamp: {value!r}") from exc


def _float(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DiagnosticError(f"Missing/non-numeric {field}")
    converted = float(value)
    if not math.isfinite(converted):
        raise DiagnosticError(f"Non-finite {field}")
    return converted


def _validate_report_probe_identity(report: dict[str, Any], probe: dict[str, Any]) -> None:
    comparisons = (
        ("symbol", report.get("symbol"), probe.get("symbol")),
        ("broker", report.get("broker"), probe.get("broker_company")),
        ("server", report.get("server"), probe.get("server")),
        ("currency", report.get("currency"), probe.get("account_currency")),
        ("terminal_build", report.get("terminal_build"), probe.get("terminal_build")),
    )
    for field, report_value, probe_value in comparisons:
        if report_value is None or probe_value is None:
            raise DiagnosticError(f"Report/probe {field} metadata is missing")
        if report_value != probe_value:
            raise DiagnosticError(
                f"Report/probe {field} mismatch: {report_value!r} != {probe_value!r}"
            )

    deposit = _float(report.get("deposit"), "report deposit")
    balance = _float(probe.get("account_balance"), "probe account balance")
    if abs(deposit - balance) > 0.005:
        raise DiagnosticError(f"Report/probe deposit mismatch: {deposit} != {balance}")
    leverage_match = re.fullmatch(r"\s*1\s*:\s*(\d+)\s*", str(report.get("leverage")))
    if leverage_match is None:
        raise DiagnosticError(f"Unsupported report leverage: {report.get('leverage')!r}")
    leverage = int(leverage_match.group(1))
    if leverage != probe.get("account_leverage"):
        raise DiagnosticError(
            f"Report/probe leverage mismatch: {leverage} != {probe.get('account_leverage')!r}"
        )


def reconstruct_trades(report: dict[str, Any], probe: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_report_probe_identity(report, probe)
    tick_size = _float(probe.get("tick_size"), "tick_size")
    min_volume = _float(probe.get("volume_min"), "volume_min")
    if tick_size <= 0.0 or min_volume <= 0.0:
        raise DiagnosticError("Tick size and minimum volume must be positive")
    entry_orders = {
        int(order["order"]): order
        for order in report.get("orders", [])
        if str(order.get("type", "")).endswith(" limit")
    }
    trade_deals = [
        deal
        for deal in report.get("deals", [])
        if deal.get("direction") in {"in", "out"} and deal.get("type") in {"buy", "sell"}
    ]
    open_deal: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    for deal in trade_deals:
        direction = deal["direction"]
        if direction == "in":
            if open_deal is not None:
                raise DiagnosticError("Overlapping entry deals cannot be paired safely")
            open_deal = deal
            continue
        if open_deal is None:
            raise DiagnosticError("Exit deal found without a preceding entry")

        order_id = open_deal.get("order")
        order = entry_orders.get(int(order_id)) if order_id is not None else None
        if order is None:
            raise DiagnosticError(f"Entry order geometry missing for order {order_id}")
        side = str(open_deal["type"])
        if (side == "buy" and deal["type"] != "sell") or (
            side == "sell" and deal["type"] != "buy"
        ):
            raise DiagnosticError("Entry/exit directions are not symmetric")

        entry_time = _parse_time(str(open_deal["time"]))
        exit_time = _parse_time(str(deal["time"]))
        entry_price = _float(open_deal.get("price"), "entry price")
        exit_price = _float(deal.get("price"), "exit price")
        requested_entry = _float(order.get("price"), "requested entry")
        original_stop = _float(order.get("sl"), "original stop")
        original_target = _float(order.get("tp"), "original target")
        volume = _float(open_deal.get("volume"), "entry volume")
        exit_volume = _float(deal.get("volume"), "exit volume")
        if abs(volume - exit_volume) > 1e-9:
            raise DiagnosticError("Partial/mismatched volume requires position-ID aggregation")

        risk_price = (
            entry_price - original_stop if side == "buy" else original_stop - entry_price
        )
        if risk_price <= 0.0:
            raise DiagnosticError("Original stop does not define positive risk")
        probe_pnl_field = (
            "min_volume_one_tick_buy_pnl"
            if side == "buy"
            else "min_volume_one_tick_sell_pnl"
        )
        one_tick_min_volume_pnl = abs(
            _float(probe.get(probe_pnl_field), probe_pnl_field)
        )
        money_per_tick_per_lot = one_tick_min_volume_pnl / min_volume
        if money_per_tick_per_lot <= 0.0:
            raise DiagnosticError(
                f"OrderCalcProfit-derived tick value is not positive for {side}"
            )
        initial_risk_money = (
            risk_price / tick_size * money_per_tick_per_lot * volume
        )
        cost_fields = ("commission", "swap", "fee")
        cost_components = {
            field: sum(
                _float(item.get(field) if item.get(field) is not None else 0.0, field)
                for item in (open_deal, deal)
            )
            for field in cost_fields
        }
        costs = sum(cost_components.values())
        gross_profit = sum(
            _float(item.get("profit") or 0.0, "profit") for item in (open_deal, deal)
        )
        net_profit = gross_profit + costs
        adverse_entry = (
            entry_price - requested_entry if side == "buy" else requested_entry - entry_price
        )

        comment = str(deal.get("comment", "")).strip().lower()
        exit_kind = "TP" if comment.startswith("tp ") else "SL" if comment.startswith("sl ") else "OTHER"
        reference_match = re.match(r"(?:tp|sl)\s+([-+]?\d+(?:[.,]\d+)?)", comment)
        exit_reference = (
            float(reference_match.group(1).replace(",", ".")) if reference_match else None
        )
        adverse_exit_ticks = None
        if exit_reference is not None:
            adverse_exit = (
                exit_reference - exit_price if side == "buy" else exit_price - exit_reference
            )
            adverse_exit_ticks = adverse_exit / tick_size

        trades.append(
            {
                "trade_index": len(trades) + 1,
                "entry_order": int(order_id),
                "side": side,
                "entry_time": entry_time.isoformat(sep=" "),
                "exit_time": exit_time.isoformat(sep=" "),
                "duration_seconds": int((exit_time - entry_time).total_seconds()),
                "volume": volume,
                "requested_entry": requested_entry,
                "entry_price": entry_price,
                "original_stop": original_stop,
                "original_target": original_target,
                "exit_price": exit_price,
                "exit_kind": exit_kind,
                "exit_comment": comment,
                "entry_slippage_ticks_adverse": adverse_entry / tick_size,
                "exit_slippage_ticks_adverse": adverse_exit_ticks,
                "gross_profit": gross_profit,
                "commission": cost_components["commission"],
                "swap": cost_components["swap"],
                "fee": cost_components["fee"],
                "costs": costs,
                "net_profit": net_profit,
                "initial_risk_money": initial_risk_money,
                "risk_valuation": "order_calc_profit_probe",
                "net_r": net_profit / initial_risk_money,
                "mfe_r": None,
                "mae_r": None,
            }
        )
        open_deal = None

    if open_deal is not None:
        raise DiagnosticError("Unclosed entry deal found")
    return trades


def _report_window(report: dict[str, Any]) -> tuple[datetime, datetime]:
    match = re.search(
        r"\((\d{4}\.\d{2}\.\d{2})\s*-\s*(\d{4}\.\d{2}\.\d{2})\)",
        str(report.get("period", "")),
    )
    if match is None:
        raise DiagnosticError(f"Cannot parse report window: {report.get('period')!r}")
    start = datetime.strptime(match.group(1), "%Y.%m.%d")
    end = datetime.strptime(match.group(2), "%Y.%m.%d")
    if start >= end:
        raise DiagnosticError("Report window must have start < end")
    return start, end


def _calendar_daily_r(
    trades: list[dict[str, Any]], report: dict[str, Any]
) -> list[float]:
    by_day: dict[Any, float] = defaultdict(float)
    start, end = _report_window(report)
    for trade in trades:
        day = datetime.fromisoformat(str(trade["exit_time"])).date()
        if day < start.date() or day >= end.date():
            raise DiagnosticError(f"Trade exit {day} is outside the half-open report window")
        by_day[day] += float(trade["net_r"])
    values: list[float] = []
    current = start.date()
    while current < end.date():
        values.append(by_day.get(current, 0.0))
        current += timedelta(days=1)
    return values


def _side_summary(trades: Iterable[dict[str, Any]], side: str) -> dict[str, Any]:
    selected = [trade for trade in trades if trade["side"] == side]
    return {
        "trades": len(selected),
        "net_profit": sum(float(trade["net_profit"]) for trade in selected),
        "net_r": sum(float(trade["net_r"]) for trade in selected),
    }


def analyze_report(
    report: dict[str, Any],
    probe: dict[str, Any],
    min_trades: int = MINIMUM_TRADES_FLOOR,
) -> dict[str, Any]:
    if min_trades < MINIMUM_TRADES_FLOOR:
        raise ValueError(
            f"min_trades cannot be below the fail-closed floor of {MINIMUM_TRADES_FLOOR}"
        )
    trades = reconstruct_trades(report, probe)
    if not trades:
        raise DiagnosticError("No closed trades were reconstructed")

    trade_count = len(trades)
    full_tp = sum(trade["exit_kind"] == "TP" for trade in trades)
    stop_exits = sum(trade["exit_kind"] == "SL" for trade in trades)
    tp_low, tp_high = wilson_interval(full_tp, trade_count)
    total_net = sum(float(trade["net_profit"]) for trade in trades)
    total_net_r = sum(float(trade["net_r"]) for trade in trades)
    positives = sorted(
        (float(trade["net_profit"]) for trade in trades if float(trade["net_profit"]) > 0.0),
        reverse=True,
    )
    gross_positive = sum(positives)
    largest_positive = positives[0] if positives else 0.0
    concentration = largest_positive / gross_positive if gross_positive > 0.0 else None
    durations = [int(trade["duration_seconds"]) for trade in trades]
    daily_r = _calendar_daily_r(trades, report)
    ci_low, ci_high = moving_block_bootstrap_mean_ci(daily_r)

    def _break_even_rate(field: str) -> float | None:
        tp_values = [float(trade[field]) for trade in trades if trade["exit_kind"] == "TP"]
        non_tp_values = [
            float(trade[field]) for trade in trades if trade["exit_kind"] != "TP"
        ]
        if not tp_values or not non_tp_values:
            return None
        tp_mean = mean(tp_values)
        non_tp_mean = mean(non_tp_values)
        denominator = tp_mean - non_tp_mean
        if tp_mean > 0.0 and non_tp_mean < 0.0 and denominator > 0.0:
            return -non_tp_mean / denominator
        return None

    break_even_tp_rate_usd = _break_even_rate("net_profit")
    break_even_tp_rate_r = _break_even_rate("net_r")

    entry_limits = [
        order
        for order in report.get("orders", [])
        if str(order.get("type", "")).endswith(" limit")
    ]
    filled_limits = sum(order.get("state") == "filled" for order in entry_limits)
    trade_deals = [
        deal
        for deal in report.get("deals", [])
        if deal.get("direction") in {"in", "out"}
    ]
    commissions_raw = [deal.get("commission") for deal in trade_deals]
    fees_raw = [deal.get("fee") for deal in trade_deals]

    findings: list[dict[str, Any]] = []
    reported_trade_count = report.get("trades")
    if reported_trade_count != trade_count:
        findings.append(
            {
                "severity": "BLOCKER",
                "code": "RECONSTRUCTED_TRADE_COUNT_MISMATCH",
                "reconstructed": trade_count,
                "reported": reported_trade_count,
            }
        )
    reported_net = _float(report.get("net_profit"), "report net profit")
    if abs(total_net - reported_net) > 0.011:
        findings.append(
            {
                "severity": "BLOCKER",
                "code": "RECONSTRUCTED_NET_PROFIT_MISMATCH",
                "reconstructed": total_net,
                "reported": reported_net,
            }
        )
    reconstructed_positive = sum(float(trade["net_profit"]) > 1e-12 for trade in trades)
    reconstructed_breakeven = sum(abs(float(trade["net_profit"])) <= 1e-12 for trade in trades)
    reconstructed_losers = sum(float(trade["net_profit"]) < -1e-12 for trade in trades)
    reconstructed_winners = reconstructed_positive + reconstructed_breakeven
    if (
        report.get("winners") != reconstructed_winners
        or report.get("losers") != reconstructed_losers
    ):
        findings.append(
            {
                "severity": "BLOCKER",
                "code": "RECONSTRUCTED_WIN_LOSS_COUNT_MISMATCH",
                "reconstructed": [reconstructed_winners, reconstructed_losers],
                "reported": [report.get("winners"), report.get("losers")],
            }
        )
    if trade_count < min_trades:
        findings.append(
            {
                "severity": "EVIDENCE_BLOCKER",
                "code": "INSUFFICIENT_SAMPLE_SIZE",
                "actual": trade_count,
                "minimum": min_trades,
            }
        )
    real_ticks_pct = report.get("real_ticks_pct")
    if real_ticks_pct != 100.0:
        findings.append(
            {"severity": "BLOCKER", "code": "DATA_NOT_100_PERCENT_REAL_TICKS", "actual": real_ticks_pct}
        )
    if not commissions_raw or any(value is None for value in commissions_raw):
        findings.append(
            {"severity": "BLOCKER", "code": "COMMISSION_FIELD_MISSING"}
        )
    elif all(abs(float(value)) < 1e-12 for value in commissions_raw):
        findings.append(
            {"severity": "BLOCKER", "code": "COMMISSION_UNVERIFIED_ZERO"}
        )
    if not fees_raw or any(value is None for value in fees_raw):
        findings.append(
            {"severity": "BLOCKER", "code": "DEAL_FEE_NOT_EXPORTED"}
        )
    if concentration is not None and concentration > 0.40:
        findings.append(
            {"severity": "FAIL", "code": "WINNER_CONCENTRATION", "actual": concentration}
        )
    if ci_low <= 0.0:
        findings.append(
            {"severity": "FAIL", "code": "BOOTSTRAP_LOWER_BOUND_NOT_POSITIVE", "actual": ci_low}
        )
    if total_net < 0.0 or float(report.get("profit_factor", 0.0)) < 1.0:
        findings.append(
            {"severity": "FAIL", "code": "NEGATIVE_EXPECTANCY", "net_profit": total_net}
        )
    if break_even_tp_rate_r is not None and tp_low <= break_even_tp_rate_r:
        findings.append(
            {
                "severity": "FAIL",
                "code": "TP_PROBABILITY_LOWER_BOUND_BELOW_BREAK_EVEN",
                "wilson_low": tp_low,
                "break_even_tp_rate_r": break_even_tp_rate_r,
            }
        )

    probe_tick_value = _float(probe.get("tick_value"), "tick_value")
    min_volume = _float(probe.get("volume_min"), "volume_min")
    one_tick_min = abs(_float(probe.get("min_volume_one_tick_buy_pnl"), "one-tick PnL"))
    derived_tick_value = one_tick_min / min_volume if min_volume > 0.0 else 0.0
    if derived_tick_value > 0.0 and abs(probe_tick_value - derived_tick_value) / derived_tick_value > 0.01:
        findings.append(
            {
                "severity": "WARN",
                "code": "SYMBOL_TICK_VALUE_DISAGREES_WITH_ORDER_CALC_PROFIT",
                "symbol_property": probe_tick_value,
                "order_calc_derived": derived_tick_value,
            }
        )

    technical_invalid = any(finding["severity"] == "BLOCKER" for finding in findings)
    negative_expectancy = total_net < 0.0 or float(report.get("profit_factor", 0.0)) < 1.0
    if negative_expectancy:
        performance_assessment = "REJECTED"
    elif any(finding["severity"] in {"FAIL", "EVIDENCE_BLOCKER"} for finding in findings):
        performance_assessment = "INCONCLUSIVE"
    else:
        performance_assessment = "ELIGIBLE_FOR_NEXT_GATE"

    if technical_invalid:
        verdict = "INVALID_TECHNICAL"
    elif negative_expectancy:
        verdict = "REJECTED"
    elif any(finding["severity"] in {"FAIL", "EVIDENCE_BLOCKER"} for finding in findings):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "ELIGIBLE_FOR_NEXT_GATE"

    report_start, report_end = _report_window(report)
    timeframe = str(report.get("period", "")).split(" ", 1)[0]

    return {
        "schema": SCHEMA,
        "report": report.get("report"),
        "symbol": report.get("symbol"),
        "period": report.get("period"),
        "history_quality": report.get("history_quality"),
        "real_ticks_pct": real_ticks_pct,
        "verdict": verdict,
        "technical_validity": "INVALID" if technical_invalid else "VALID",
        "performance_assessment": performance_assessment,
        "provenance": {
            "broker": report.get("broker"),
            "server": report.get("server"),
            "symbol": report.get("symbol"),
            "timeframe": timeframe,
            "window": {
                "start": report_start.date().isoformat(),
                "end": report_end.date().isoformat(),
            },
            "currency": report.get("currency"),
            "terminal_build": report.get("terminal_build"),
            "deposit": report.get("deposit"),
            "leverage": report.get("leverage"),
        },
        "policy": {
            "minimum_trades": min_trades,
            "minimum_trades_fail_closed_floor": MINIMUM_TRADES_FLOOR,
            "bootstrap": {
                "method": "moving_block_calendar_daily_net_r",
                "block_length": 5,
                "replications": 10000,
                "seed": 20260805,
            },
        },
        "summary": {
            "trades": trade_count,
            "full_tp": full_tp,
            "stop_exits": stop_exits,
            "tp_rate": full_tp / trade_count,
            "tp_wilson_95": [tp_low, tp_high],
            "break_even_tp_rate_usd": break_even_tp_rate_usd,
            "break_even_tp_rate_r": break_even_tp_rate_r,
            "net_profit_reconstructed": total_net,
            "net_profit_report": reported_net,
            "net_profit_reconciliation_delta": total_net - reported_net,
            "net_r_sum": total_net_r,
            "daily_net_r_mean": mean(daily_r),
            "daily_net_r_block_bootstrap_95": [ci_low, ci_high],
            "gross_positive": gross_positive,
            "largest_positive": largest_positive,
            "largest_positive_share": concentration,
            "net_without_largest_positive": total_net - largest_positive,
            "positive_trades": reconstructed_positive,
            "breakeven_trades": reconstructed_breakeven,
            "negative_trades": reconstructed_losers,
            "median_duration_seconds": median(durations),
            "exits_within_2_minutes": sum(duration <= 120 for duration in durations),
            "exits_under_5_minutes": sum(duration < 300 for duration in durations),
            "entry_limit_orders": len(entry_limits),
            "filled_limit_orders": filled_limits,
            "limit_fill_rate": filled_limits / len(entry_limits) if entry_limits else None,
            "long": _side_summary(trades, "buy"),
            "short": _side_summary(trades, "sell"),
            "mfe_mae_available": False,
        },
        "findings": findings,
        "trades": trades,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--min-trades", type=int, default=MINIMUM_TRADES_FLOOR)
    args = parser.parse_args()
    try:
        result = analyze_report(
            parse_report(args.report), _load_probe(args.probe), min_trades=args.min_trades
        )
    except (DiagnosticError, ValueError) as exc:
        print(json.dumps({"schema": SCHEMA, "verdict": "INVALID_TECHNICAL", "error": str(exc)}))
        return 2
    if args.summary_only:
        result = {key: result[key] for key in result if key != "trades"}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
