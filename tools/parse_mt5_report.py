#!/usr/bin/env python3
"""Extract comparable metrics from MT5 Strategy Tester HTML reports."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Iterable
import unicodedata


class _CellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[str] = []
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._inside_cell = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized == "tr":
            self._current_row = []
        elif normalized in {"td", "th"}:
            self._inside_cell = True
            self._parts = []
        elif normalized == "br" and self._inside_cell:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._inside_cell:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"td", "th"} and self._inside_cell:
            value = " ".join("".join(self._parts).split())
            self.cells.append(value)
            if self._current_row is not None:
                self._current_row.append(value)
            self._inside_cell = False
            self._parts = []
        elif normalized == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None


LABELS = {
    "expert": ("Expert:",),
    "symbol": ("Symbole:", "Symbol:"),
    "period": ("Période:", "Period:"),
    "deposit": ("Dépôt initial:", "Initial Deposit:"),
    "leverage": ("Levier:", "Leverage:"),
    "history_quality": ("Qualité de l'Historique:", "History Quality:"),
    "bars": ("Barres:", "Bars:"),
    "ticks": ("Tiques:", "Ticks:"),
    "net_profit": ("Profit Total Net:", "Total Net Profit:"),
    "gross_profit": ("Profit brut:", "Gross Profit:"),
    "gross_loss": ("Perte brut:", "Gross Loss:"),
    "equity_drawdown_max": ("Fond Drawdown Maximal:", "Equity Drawdown Maximal:"),
    "profit_factor": ("Facteur de profit:", "Profit Factor:"),
    "expected_payoff": ("Remboursement attendu:", "Expected Payoff:"),
    "sharpe": ("Ratio de Sharpe:", "Sharpe Ratio:"),
    "on_tester": ("Résultat de la fonction OnTester:", "OnTester result:"),
    "trades": ("Nb trades:", "Total Trades:"),
    "winners": ("Positions gagnantes (% du total):", "Profit Trades (% of total):"),
    "losers": ("Positions perdantes (% du total):", "Loss Trades (% of total):"),
}


def _read_report(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _find_value(rows: list[list[str]], aliases: Iterable[str]) -> str:
    for alias in aliases:
        for row in rows:
            for index, cell in enumerate(row):
                if cell != alias:
                    continue
                for candidate in row[index + 1 :]:
                    if candidate:
                        return candidate
                raise ValueError(f"MT5 report value missing after label: {alias}")
    raise ValueError(f"MT5 report label not found: {', '.join(aliases)}")


def _find_optional_value(rows: list[list[str]], aliases: Iterable[str]) -> str | None:
    try:
        return _find_value(rows, aliases)
    except ValueError as exc:
        if "label not found" in str(exc):
            return None
        raise


def _number(value: str) -> float:
    match = re.search(r"[-+]?\d[\d\s\u00a0]*(?:[.,]\d+)?", value)
    if not match:
        raise ValueError(f"No numeric value found in: {value!r}")
    normalized = re.sub(r"[\s\u00a0]", "", match.group(0)).replace(",", ".")
    return float(normalized)


def _optional_number(value: str) -> float | None:
    if not value.strip():
        return None
    return _number(value)


def _section_rows(
    rows: list[list[str]], section_aliases: set[str]
) -> tuple[list[str], list[list[str]]]:
    for section_index, row in enumerate(rows):
        if len(row) != 1 or row[0] not in section_aliases:
            continue
        header_index = section_index + 1
        while header_index < len(rows) and len(rows[header_index]) <= 1:
            header_index += 1
        if header_index >= len(rows):
            return [], []
        header = rows[header_index]
        data: list[list[str]] = []
        for candidate in rows[header_index + 1 :]:
            if len(candidate) == 1:
                break
            if len(candidate) == len(header):
                data.append(candidate)
        return header, data
    return [], []


def _normalized_header(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_value.lower())


def _column_indexes(
    header: list[str], aliases: dict[str, set[str]], required: set[str]
) -> dict[str, int]:
    normalized = [_normalized_header(value) for value in header]
    indexes: dict[str, int] = {}
    for field, field_aliases in aliases.items():
        matches = [index for index, value in enumerate(normalized) if value in field_aliases]
        if len(matches) > 1:
            raise ValueError(f"Duplicate MT5 report column for {field}: {header}")
        if matches:
            indexes[field] = matches[0]
    missing = sorted(required - indexes.keys())
    if missing:
        raise ValueError(f"Missing MT5 report columns {missing}: {header}")
    return indexes


def _parse_order_rows(rows: list[list[str]]) -> list[dict[str, object]]:
    header, data = _section_rows(rows, {"Ordres", "Orders"})
    if not header:
        return []
    indexes = _column_indexes(
        header,
        {
            "open_time": {"heuredouverture", "opentime"},
            "order": {"ordre", "order"},
            "symbol": {"symbole", "symbol"},
            "type": {"type"},
            "volume": {"volume"},
            "price": {"prix", "price"},
            "sl": {"sl"},
            "tp": {"tp"},
            "close_time": {"heure", "time"},
            "state": {"etat", "state"},
            "comment": {"commentaire", "comment"},
        },
        {
            "open_time",
            "order",
            "symbol",
            "type",
            "volume",
            "price",
            "sl",
            "tp",
            "close_time",
            "state",
            "comment",
        },
    )
    parsed: list[dict[str, object]] = []
    for row in data:
        volume_parts = [part.strip() for part in row[indexes["volume"]].split("/", 1)]
        parsed.append(
            {
                "open_time": row[indexes["open_time"]],
                "order": int(_number(row[indexes["order"]])),
                "symbol": row[indexes["symbol"]],
                "type": row[indexes["type"]].lower(),
                "volume_requested": _optional_number(volume_parts[0]),
                "volume_filled": (
                    _optional_number(volume_parts[1]) if len(volume_parts) == 2 else None
                ),
                "price": _optional_number(row[indexes["price"]]),
                "sl": _optional_number(row[indexes["sl"]]),
                "tp": _optional_number(row[indexes["tp"]]),
                "close_time": row[indexes["close_time"]],
                "state": row[indexes["state"]].lower(),
                "comment": row[indexes["comment"]],
            }
        )
    return parsed


def _parse_deal_rows(rows: list[list[str]]) -> list[dict[str, object]]:
    header, data = _section_rows(rows, {"Transactions", "Deals"})
    if not header:
        return []
    indexes = _column_indexes(
        header,
        {
            "time": {"heure", "time"},
            "deal": {"operation", "deal"},
            "symbol": {"symbole", "symbol"},
            "type": {"type"},
            "direction": {"direction"},
            "volume": {"volume"},
            "price": {"prix", "price"},
            "order": {"ordre", "order"},
            "commission": {"commission"},
            "fee": {"frais", "fee"},
            "swap": {"echange", "swap"},
            "profit": {"profit"},
            "balance": {"solde", "balance"},
            "comment": {"commentaire", "comment"},
        },
        {
            "time",
            "deal",
            "symbol",
            "type",
            "direction",
            "volume",
            "price",
            "order",
            "commission",
            "swap",
            "profit",
            "balance",
            "comment",
        },
    )
    parsed: list[dict[str, object]] = []
    for row in data:
        parsed.append(
            {
                "time": row[indexes["time"]],
                "deal": int(_number(row[indexes["deal"]])),
                "symbol": row[indexes["symbol"]],
                "type": row[indexes["type"]].lower(),
                "direction": row[indexes["direction"]].lower(),
                "volume": _optional_number(row[indexes["volume"]]),
                "price": _optional_number(row[indexes["price"]]),
                "order": (
                    int(_number(row[indexes["order"]]))
                    if row[indexes["order"]]
                    else None
                ),
                "commission": _optional_number(row[indexes["commission"]]),
                "fee": (
                    _optional_number(row[indexes["fee"]]) if "fee" in indexes else None
                ),
                "swap": _optional_number(row[indexes["swap"]]),
                "profit": _optional_number(row[indexes["profit"]]),
                "balance": _optional_number(row[indexes["balance"]]),
                "comment": row[indexes["comment"]],
            }
        )
    return parsed


def _extract_inputs(cells: list[str]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for cell in cells:
        if not re.fullmatch(r"Inp[A-Za-z0-9_]+=.*", cell):
            continue
        name, value = cell.split("=", 1)
        if name in inputs:
            raise ValueError(f"Duplicate MT5 input in report: {name}")
        inputs[name] = value
    return inputs


def parse_report(path: Path) -> dict[str, object]:
    parser = _CellParser()
    parser.feed(_read_report(path))
    raw_values = {key: _find_value(parser.rows, aliases) for key, aliases in LABELS.items()}

    drawdown_raw = raw_values["equity_drawdown_max"]
    percentage = re.search(r"\(([-+]?\d+(?:[.,]\d+)?)%\)", drawdown_raw)
    real_ticks_match = re.search(
        r"([-+]?\d+(?:[.,]\d+)?)\s*%\s*(?:ticks?\s+r[eé]el|real\s+ticks?)",
        raw_values["history_quality"],
        flags=re.IGNORECASE,
    )
    server_build = next(
        (cell for cell in parser.cells if re.search(r"\(Build\s+\d+\)", cell)),
        None,
    )
    server_build_match = (
        re.fullmatch(r"(.+?)\s*\(Build\s+(\d+)\)", server_build)
        if server_build is not None
        else None
    )
    return {
        "report": str(path.resolve()),
        "expert": raw_values["expert"],
        "broker": _find_optional_value(parser.rows, ("Courtier:", "Broker:")),
        "server_build": server_build,
        "server": server_build_match.group(1).strip() if server_build_match else None,
        "terminal_build": int(server_build_match.group(2)) if server_build_match else None,
        "currency": _find_optional_value(parser.rows, ("Devise:", "Currency:")),
        "symbol": raw_values["symbol"],
        "period": raw_values["period"],
        "inputs": _extract_inputs(parser.cells),
        "deposit": _number(raw_values["deposit"]),
        "leverage": raw_values["leverage"],
        "history_quality": raw_values["history_quality"],
        "real_ticks_pct": (
            float(real_ticks_match.group(1).replace(",", "."))
            if real_ticks_match
            else None
        ),
        "bars": int(_number(raw_values["bars"])),
        "ticks": int(_number(raw_values["ticks"])),
        "net_profit": _number(raw_values["net_profit"]),
        "gross_profit": _number(raw_values["gross_profit"]),
        "gross_loss": _number(raw_values["gross_loss"]),
        "equity_drawdown_max": _number(drawdown_raw),
        "equity_drawdown_max_pct": (
            float(percentage.group(1).replace(",", ".")) if percentage else None
        ),
        "profit_factor": _number(raw_values["profit_factor"]),
        "expected_payoff": _number(raw_values["expected_payoff"]),
        "sharpe": _number(raw_values["sharpe"]),
        "on_tester": _number(raw_values["on_tester"]),
        "trades": int(_number(raw_values["trades"])),
        "winners": int(_number(raw_values["winners"])),
        "losers": int(_number(raw_values["losers"])),
        "orders": _parse_order_rows(parser.rows),
        "deals": _parse_deal_rows(parser.rows),
    }


def _print_table(results: list[dict[str, object]]) -> None:
    columns = (
        ("report", "Report"),
        ("history_quality", "Quality"),
        ("trades", "Trades"),
        ("winners", "Wins"),
        ("net_profit", "Net"),
        ("profit_factor", "PF"),
        ("expected_payoff", "Payoff"),
        ("equity_drawdown_max_pct", "EqDD%"),
        ("sharpe", "Sharpe"),
        ("on_tester", "OnTester"),
    )
    rows = []
    for result in results:
        row = []
        for key, _ in columns:
            value = result[key]
            if key == "report":
                value = Path(str(value)).stem
            elif isinstance(value, float):
                value = f"{value:.4f}"
            row.append(str(value))
        rows.append(row)

    widths = [len(title) for _, title in columns]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]
    print("  ".join(title.ljust(width) for (_, title), width in zip(columns, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("reports", type=Path, nargs="+")
    argument_parser.add_argument("--json", action="store_true", dest="as_json")
    args = argument_parser.parse_args()

    results = [parse_report(path) for path in args.reports]
    if args.as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        _print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
