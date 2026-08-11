#!/usr/bin/env python3
"""Evaluate several MT5 component reports with symbol-specific costs.

This tool deliberately does not present independently tested symbols as a
synchronized portfolio backtest.  It validates that every report uses the
same window and high-quality real ticks, applies an explicit cost model per
symbol, then produces a deterministic component-level research gate.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Iterable

try:  # Support both ``python -m tools...`` and direct script execution.
    from tools.cost_adjustment import CostAdjustmentError, adjust_report
    from tools.parse_mt5_report import parse_report
except ModuleNotFoundError:  # pragma: no cover - exercised by CLI smoke tests
    from cost_adjustment import CostAdjustmentError, adjust_report
    from parse_mt5_report import parse_report


class PortfolioEvaluationError(ValueError):
    """Raised when reports cannot be compared without unsafe assumptions."""


def _finite_nonnegative(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioEvaluationError(f"{name} must be a number") from exc
    if not math.isfinite(result) or result < 0.0:
        raise PortfolioEvaluationError(f"{name} must be finite and non-negative")
    return result


def parse_symbol_values(values: Iterable[str], option: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for raw in values:
        symbol, separator, value = raw.partition("=")
        symbol = symbol.strip().upper()
        if separator != "=" or not symbol or not value.strip():
            raise PortfolioEvaluationError(
                f"{option} expects SYMBOL=AMOUNT, got {raw!r}"
            )
        if symbol in result:
            raise PortfolioEvaluationError(f"duplicate {option} for {symbol}")
        result[symbol] = _finite_nonnegative(value, f"{option} {symbol}")
    return result


def extract_window(period: object) -> tuple[str, str]:
    dates = re.findall(r"\b\d{4}[.-]\d{2}[.-]\d{2}\b", str(period))
    if len(dates) != 2:
        raise PortfolioEvaluationError(
            f"cannot extract an exact test window from period {period!r}"
        )
    normalized = [value.replace("-", ".") for value in dates]
    try:
        for value in normalized:
            datetime.strptime(value, "%Y.%m.%d")
    except ValueError as exc:
        raise PortfolioEvaluationError(f"invalid period dates: {period!r}") from exc
    if normalized[1] < normalized[0]:
        raise PortfolioEvaluationError(f"reversed period dates: {period!r}")
    return normalized[0], normalized[1]


def _scenario_summary(
    components: list[dict[str, object]], scenario_name: str
) -> dict[str, object]:
    positions: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    for component in components:
        scenario = component["scenarios"][scenario_name]  # type: ignore[index]
        symbol = str(component["symbol"])
        rows = scenario["positions"]  # type: ignore[index]
        positions.extend(rows)
        component_rows.append(
            {
                "additional_cost": scenario["additional_cost"],  # type: ignore[index]
                "adjusted_net": scenario["adjusted_net"],  # type: ignore[index]
                "profit_factor": scenario["profit_factor"],  # type: ignore[index]
                "symbol": symbol,
                "trades": scenario["trades"],  # type: ignore[index]
            }
        )

    values = [float(row["adjusted_net"]) for row in positions]
    winners = sorted((value for value in values if value > 0.0), reverse=True)
    gross_profit = sum(winners)
    gross_loss = sum(value for value in values if value < 0.0)
    net = sum(values)
    best = winners[0] if winners else 0.0
    return {
        "adjusted_gross_loss": gross_loss,
        "adjusted_gross_profit": gross_profit,
        "adjusted_net": net,
        "all_components_positive": all(
            float(row["adjusted_net"]) > 0.0 for row in component_rows
        ),
        "best_position_profit": best if winners else None,
        "best_share_of_gross_profit": best / gross_profit if gross_profit else None,
        "components": sorted(component_rows, key=lambda row: str(row["symbol"])),
        "net_without_best": net - best if winners else net,
        "profit_factor": gross_profit / -gross_loss if gross_loss < 0.0 else None,
        "trades": len(values),
        "winners": len(winners),
    }


def evaluate_reports(
    reports: list[dict[str, object]],
    *,
    normal_costs: dict[str, float],
    stress_costs: dict[str, float] | None = None,
    normal_slippage: dict[str, float] | None = None,
    stress_slippage: dict[str, float] | None = None,
    min_real_ticks_pct: float = 99.0,
    min_trades_per_30d: float = 10.0,
    max_trades_per_30d: float = 80.0,
    min_normal_profit_factor: float = 1.20,
    min_stress_profit_factor: float = 1.00,
    max_best_share_of_gross_profit: float = 0.35,
) -> dict[str, object]:
    if not reports:
        raise PortfolioEvaluationError("at least one report is required")
    normal_slippage = normal_slippage or {}
    stress_slippage = stress_slippage or {}
    stress_costs = stress_costs or {}

    symbols: set[str] = set()
    windows: set[tuple[str, str]] = set()
    currencies: set[str] = set()
    adjusted_components: list[dict[str, object]] = []
    component_metadata: list[dict[str, object]] = []

    for index, report in enumerate(reports):
        symbol = str(report.get("symbol", "")).strip().upper()
        if not symbol:
            raise PortfolioEvaluationError(f"report {index} has no symbol")
        if symbol in symbols:
            raise PortfolioEvaluationError(f"duplicate component report for {symbol}")
        symbols.add(symbol)
        if symbol not in normal_costs:
            raise PortfolioEvaluationError(
                f"missing explicit normal round-turn cost for {symbol}"
            )

        real_ticks = report.get("real_ticks_pct")
        if real_ticks is None or float(real_ticks) < min_real_ticks_pct:
            raise PortfolioEvaluationError(
                f"{symbol} real tick quality is {real_ticks!r}, required >= "
                f"{min_real_ticks_pct:.2f}%"
            )
        window = extract_window(report.get("period"))
        windows.add(window)
        currency = str(report.get("currency", "")).strip().upper()
        if not currency:
            raise PortfolioEvaluationError(f"{symbol} report currency is missing")
        currencies.add(currency)

        adjusted = adjust_report(
            report,
            normal_round_turn_cost_per_lot=normal_costs[symbol],
            stress_round_turn_cost_per_lot=stress_costs.get(
                symbol, normal_costs[symbol]
            ),
            normal_extra_slippage_cost_per_lot=normal_slippage.get(symbol, 0.0),
            stress_extra_slippage_cost_per_lot=stress_slippage.get(
                symbol, normal_slippage.get(symbol, 0.0)
            ),
        )
        adjusted_components.append(adjusted)
        component_metadata.append(
            {
                "currency": currency,
                "deposit": report.get("deposit"),
                "equity_drawdown_max_pct": report.get("equity_drawdown_max_pct"),
                "normal_cost_per_lot": normal_costs[symbol],
                "normal_slippage_per_lot": normal_slippage.get(symbol, 0.0),
                "real_ticks_pct": float(real_ticks),
                "report": report.get("report"),
                "stress_cost_per_lot": stress_costs.get(symbol, normal_costs[symbol]),
                "stress_slippage_per_lot": stress_slippage.get(
                    symbol, normal_slippage.get(symbol, 0.0)
                ),
                "symbol": symbol,
            }
        )

    if len(windows) != 1:
        raise PortfolioEvaluationError(f"component windows differ: {sorted(windows)}")
    if len(currencies) != 1:
        raise PortfolioEvaluationError(
            f"component account currencies differ: {sorted(currencies)}"
        )
    unused_costs = set(normal_costs) - symbols
    if unused_costs:
        raise PortfolioEvaluationError(
            f"normal costs supplied for absent symbols: {sorted(unused_costs)}"
        )

    window_start, window_end = next(iter(windows))
    start_date = datetime.strptime(window_start, "%Y.%m.%d")
    end_date = datetime.strptime(window_end, "%Y.%m.%d")
    calendar_days = (end_date - start_date).days + 1
    normal = _scenario_summary(adjusted_components, "normal")
    stress = _scenario_summary(adjusted_components, "stress")
    trades_per_30d = float(normal["trades"]) * 30.0 / calendar_days

    normal_pf = normal["profit_factor"]
    stress_pf = stress["profit_factor"]
    concentration = normal["best_share_of_gross_profit"]
    checks = {
        "all_components_positive_normal": normal["all_components_positive"],
        "best_share_of_gross_profit": concentration is not None
        and float(concentration) <= max_best_share_of_gross_profit,
        "net_without_best_positive": float(normal["net_without_best"]) > 0.0,
        "normal_profit_factor": normal_pf is not None
        and float(normal_pf) >= min_normal_profit_factor,
        "stress_net_positive": float(stress["adjusted_net"]) > 0.0,
        "stress_profit_factor": stress_pf is not None
        and float(stress_pf) >= min_stress_profit_factor,
        "trade_frequency": min_trades_per_30d
        <= trades_per_30d
        <= max_trades_per_30d,
    }

    return {
        "candidate_gate": {
            "checks": checks,
            "passed": all(bool(value) for value in checks.values()),
            "thresholds": {
                "max_best_share_of_gross_profit": max_best_share_of_gross_profit,
                "max_trades_per_30d": max_trades_per_30d,
                "min_normal_profit_factor": min_normal_profit_factor,
                "min_stress_profit_factor": min_stress_profit_factor,
                "min_trades_per_30d": min_trades_per_30d,
            },
        },
        "components": sorted(component_metadata, key=lambda row: str(row["symbol"])),
        "currency": next(iter(currencies)),
        "limitations": [
            "Component reports were tested independently, so their sum is not a synchronized multi-symbol equity curve.",
            "Shared live portfolio exposure limits cannot be validated by separate single-symbol MT5 tester runs.",
            "This research gate is a rejection filter, not a profitability guarantee.",
        ],
        "normal": normal,
        "stress": stress,
        "trades_per_30d": trades_per_30d,
        "window": {
            "calendar_days": calendar_days,
            "end": window_end,
            "start": window_start,
        },
    }


def _clean_numbers(value: object) -> object:
    if isinstance(value, float):
        rounded = round(value, 12)
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, list):
        return [_clean_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_numbers(item) for key, item in value.items()}
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate comparable MT5 component reports with per-symbol costs"
    )
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--cost", action="append", default=[], metavar="SYMBOL=AMOUNT")
    parser.add_argument(
        "--stress-cost", action="append", default=[], metavar="SYMBOL=AMOUNT"
    )
    parser.add_argument(
        "--slippage", action="append", default=[], metavar="SYMBOL=AMOUNT"
    )
    parser.add_argument(
        "--stress-slippage", action="append", default=[], metavar="SYMBOL=AMOUNT"
    )
    parser.add_argument("--min-real-ticks-pct", type=float, default=99.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        reports = [parse_report(path) for path in args.reports]
        result = evaluate_reports(
            reports,
            normal_costs=parse_symbol_values(args.cost, "--cost"),
            stress_costs=parse_symbol_values(args.stress_cost, "--stress-cost"),
            normal_slippage=parse_symbol_values(args.slippage, "--slippage"),
            stress_slippage=parse_symbol_values(
                args.stress_slippage, "--stress-slippage"
            ),
            min_real_ticks_pct=args.min_real_ticks_pct,
        )
    except (CostAdjustmentError, OSError, PortfolioEvaluationError, ValueError) as exc:
        print(f"portfolio_evaluator: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_clean_numbers(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
