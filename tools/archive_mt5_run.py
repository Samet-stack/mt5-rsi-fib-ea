#!/usr/bin/env python3
"""Create an immutable, self-contained archive for one completed MT5 tester run.

This command does not launch MetaTrader and cannot place orders.  It freezes the
files produced by a separate tester run, verifies optional effective parameters
against the selected ``.set`` file, and writes a deterministic manifest.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping
import uuid


SCHEMA = "rsifib-mt5-run-archive/v1"
PARAMETER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


class ArchiveError(RuntimeError):
    """Raised when a run cannot be archived without weakening provenance."""


@dataclass(frozen=True)
class ArtifactSource:
    role: str
    source: Path
    relative_destination: str
    media_type: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_file(path: Path, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_file():
        raise ArchiveError(f"{label} file is missing: {candidate}")
    return candidate


def _validate_run_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ArchiveError(f"run_id must be a canonical UUID: {value!r}") from exc
    if str(parsed) != value:
        raise ArchiveError("run_id must use canonical lowercase UUID form")
    return value


def _validate_date_window(from_date: str, to_date: str) -> tuple[str, str]:
    try:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
    except ValueError as exc:
        raise ArchiveError("from_date and to_date must be ISO dates (YYYY-MM-DD)") from exc
    if start.isoformat() != from_date or end.isoformat() != to_date:
        raise ArchiveError("from_date and to_date must be canonical ISO dates")
    if start >= end:
        raise ArchiveError("to_date must be later than from_date")
    return from_date, to_date


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArchiveError(f"{field} must be a non-empty string")
    return value.strip()


def _cost_text(value: Decimal | str | int | float) -> str:
    try:
        cost = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ArchiveError("round_turn_cost_per_lot must be numeric") from exc
    if not cost.is_finite() or cost < 0:
        raise ArchiveError("round_turn_cost_per_lot must be finite and non-negative")
    normalized = format(cost.normalize(), "f")
    return "0" if Decimal(normalized) == 0 else normalized


def parse_preset(path: Path) -> dict[str, str]:
    """Parse active values from a MetaTrader ``.set`` file.

    Optimization-form values use the first field in ``value||start||step||stop``.
    Duplicate inputs are rejected instead of silently taking the last value.
    """

    preset = _require_file(path, "preset")
    try:
        text = preset.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ArchiveError(f"cannot read preset {preset}: {exc}") from exc

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if "=" not in line:
            raise ArchiveError(f"invalid preset line {line_number}: missing '='")
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not PARAMETER_NAME.fullmatch(name):
            raise ArchiveError(f"invalid preset parameter at line {line_number}: {name!r}")
        if name in values:
            raise ArchiveError(f"duplicate preset parameter: {name}")
        values[name] = raw_value.split("||", 1)[0].strip()
    if not values:
        raise ArchiveError(f"preset contains no parameters: {preset}")
    return values


def _normalize_parameter(value: Any) -> tuple[str, str]:
    if value is None:
        return "null", "null"
    if isinstance(value, bool):
        return "bool", "true" if value else "false"
    if isinstance(value, int):
        return "number", str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArchiveError("effective parameters cannot contain non-finite numbers")
        value = repr(value)
    if isinstance(value, Decimal):
        value = str(value)
    if not isinstance(value, str):
        raise ArchiveError(f"unsupported effective parameter value: {value!r}")

    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = text[1:-1]
        if isinstance(decoded, str):
            text = decoded
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return "bool", lowered
    if NUMBER.fullmatch(text):
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ArchiveError(f"invalid numeric parameter: {text!r}") from exc
        if not number.is_finite():
            raise ArchiveError(f"non-finite numeric parameter: {text!r}")
        normalized = format(number.normalize(), "f")
        return "number", "0" if number == 0 else normalized
    return "string", text


def load_effective_parameters(path: Path) -> tuple[dict[str, Any], bytes]:
    effective_path = _require_file(path, "effective parameters")
    try:
        content = effective_path.read_bytes()
        document = json.loads(content.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"cannot read effective parameters {effective_path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ArchiveError("effective parameters JSON must be an object")
    candidate = document.get("inputs", document)
    if not isinstance(candidate, dict):
        raise ArchiveError("effective parameters 'inputs' must be an object")
    if not all(isinstance(name, str) and PARAMETER_NAME.fullmatch(name) for name in candidate):
        raise ArchiveError("effective parameter names are invalid")
    return candidate, content


def compare_effective_parameters(
    preset_values: Mapping[str, Any], effective_values: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a strict, deterministic comparison of preset and effective inputs."""

    preset_names = set(preset_values)
    effective_names = set(effective_values)
    missing = sorted(preset_names - effective_names)
    unexpected = sorted(effective_names - preset_names)
    mismatched: list[dict[str, str]] = []
    for name in sorted(preset_names & effective_names):
        expected = _normalize_parameter(preset_values[name])
        actual = _normalize_parameter(effective_values[name])
        if expected != actual:
            mismatched.append(
                {
                    "name": name,
                    "preset": str(preset_values[name]),
                    "effective": str(effective_values[name]),
                }
            )
    return {
        "matched": not missing and not unexpected and not mismatched,
        "preset_count": len(preset_values),
        "effective_count": len(effective_values),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ArchiveError(f"refusing to overwrite archive artifact: {path}") from exc
    except OSError as exc:
        raise ArchiveError(f"cannot write archive artifact {path}: {exc}") from exc


def _archive_artifact(run_directory: Path, item: ArtifactSource) -> dict[str, Any]:
    try:
        content = _require_file(item.source, item.role).read_bytes()
    except OSError as exc:
        raise ArchiveError(f"cannot read {item.role} file {item.source}: {exc}") from exc
    destination = run_directory / item.relative_destination
    _write_exclusive(destination, content)
    return {
        "role": item.role,
        "path": item.relative_destination,
        "media_type": item.media_type,
        "bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def _write_manifest_atomic(run_directory: Path, manifest: dict[str, Any]) -> None:
    content = _canonical_json_bytes(manifest)
    temporary = run_directory / ".manifest.json.tmp"
    destination = run_directory / "manifest.json"
    _write_exclusive(temporary, content)
    try:
        os.replace(temporary, destination)
    except OSError as exc:
        raise ArchiveError(f"cannot finalize manifest {destination}: {exc}") from exc


def archive_mt5_run(
    *,
    root: Path,
    run_id: str,
    source: Path,
    preset: Path,
    report: Path,
    from_date: str,
    to_date: str,
    broker: str,
    symbol: str,
    timeframe: str,
    terminal_build: int,
    model: str,
    round_turn_cost_per_lot: Decimal | str | int | float,
    cost_currency: str,
    cost_verified: bool,
    seed: int,
    ex5: Path | None = None,
    log: Path | None = None,
    effective_parameters: Path | None = None,
    calendar_data: Path | None = None,
) -> dict[str, Any]:
    """Archive a completed tester run without overwriting any existing run."""

    run_id = _validate_run_id(run_id)
    from_date, to_date = _validate_date_window(from_date, to_date)
    source = _require_file(source, "source")
    preset = _require_file(preset, "preset")
    report = _require_file(report, "report")
    if ex5 is not None:
        ex5 = _require_file(ex5, "EX5")
    if log is not None:
        log = _require_file(log, "log")
    if calendar_data is not None:
        calendar_data = _require_file(calendar_data, "calendar data")
    if not isinstance(terminal_build, int) or isinstance(terminal_build, bool) or terminal_build <= 0:
        raise ArchiveError("terminal_build must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ArchiveError("seed must be a non-negative integer")
    if not isinstance(cost_verified, bool):
        raise ArchiveError("cost_verified must be boolean")
    broker = _non_empty(broker, "broker")
    symbol = _non_empty(symbol, "symbol")
    timeframe = _non_empty(timeframe, "timeframe")
    model = _non_empty(model, "model")
    cost_currency = _non_empty(cost_currency, "cost_currency")
    cost = _cost_text(round_turn_cost_per_lot)

    preset_values = parse_preset(preset)
    comparison: dict[str, Any] = {
        "performed": False,
        "matched": None,
        "preset_count": len(preset_values),
    }
    effective_content: bytes | None = None
    if effective_parameters is not None:
        effective_values, effective_content = load_effective_parameters(effective_parameters)
        comparison_result = compare_effective_parameters(preset_values, effective_values)
        comparison = {"performed": True, **comparison_result}
        if not comparison_result["matched"]:
            raise ArchiveError(
                "effective parameters do not match frozen preset: "
                + json.dumps(comparison_result, ensure_ascii=False, sort_keys=True)
            )

    run_directory = Path(root) / "runs" / run_id
    run_directory.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_directory.mkdir()
    except FileExistsError as exc:
        raise ArchiveError(f"refusing to overwrite existing run directory: {run_directory}") from exc

    artifacts = [
        ArtifactSource("source", source, "inputs/source.mq5", "text/x-mql5"),
        ArtifactSource("preset", preset, "inputs/preset.set", "text/plain"),
    ]
    if calendar_data is not None:
        artifacts.append(
            ArtifactSource(
                "calendar-data",
                calendar_data,
                "inputs/news_events.csv",
                "text/csv",
            )
        )
    if ex5 is not None:
        artifacts.append(
            ArtifactSource(
                "compiled-binary", ex5, "inputs/expert.ex5", "application/octet-stream"
            )
        )
    artifacts.append(ArtifactSource("mt5-report", report, "raw/report.htm", "text/html"))
    if log is not None:
        artifacts.append(ArtifactSource("tester-log", log, "raw/tester.log", "text/plain"))

    archived = [_archive_artifact(run_directory, item) for item in artifacts]
    if effective_content is not None:
        relative = "inputs/effective_parameters.json"
        _write_exclusive(run_directory / relative, effective_content)
        archived.append(
            {
                "role": "effective-parameters",
                "path": relative,
                "media_type": "application/json",
                "bytes": len(effective_content),
                "sha256": sha256_bytes(effective_content),
            }
        )

    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "window": {"from": from_date, "to": to_date},
        "environment": {
            "broker": broker,
            "symbol": symbol,
            "timeframe": timeframe,
            "terminal_build": terminal_build,
            "model": model,
        },
        "cost": {
            "currency": cost_currency,
            "round_turn_per_lot": cost,
            "verified": cost_verified,
        },
        "seed": seed,
        "parameter_comparison": comparison,
        "artifacts": archived,
    }
    _write_manifest_atomic(run_directory, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/experiments_v4"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ex5", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--effective-parameters", type=Path)
    parser.add_argument(
        "--calendar-data",
        type=Path,
        help="Exact NEWS_TESTER_FILE input used by the run, archived with SHA-256",
    )
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--broker", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--terminal-build", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--round-turn-cost-per-lot", required=True)
    parser.add_argument("--cost-currency", default="USD")
    parser.add_argument("--cost-verified", action="store_true")
    parser.add_argument("--seed", type=int, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        manifest = archive_mt5_run(
            root=args.root,
            run_id=args.run_id,
            source=args.source,
            preset=args.preset,
            report=args.report,
            ex5=args.ex5,
            log=args.log,
            effective_parameters=args.effective_parameters,
            calendar_data=args.calendar_data,
            from_date=args.from_date,
            to_date=args.to_date,
            broker=args.broker,
            symbol=args.symbol,
            timeframe=args.timeframe,
            terminal_build=args.terminal_build,
            model=args.model,
            round_turn_cost_per_lot=args.round_turn_cost_per_lot,
            cost_currency=args.cost_currency,
            cost_verified=args.cost_verified,
            seed=args.seed,
        )
    except ArchiveError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
