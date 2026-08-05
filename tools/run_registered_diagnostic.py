#!/usr/bin/env python3
"""Run one immutable, offline MT5 report diagnostic through the V3 registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.diagnostic_analyzer import DiagnosticError, _load_probe, analyze_report
from tools.experiment_registry import (
    ExperimentRegistry,
    RegistryError,
    _read_json_object,
    validate_spec,
)
from tools.parse_mt5_report import parse_report


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _project_relative(project_root: Path, path: Path) -> str:
    resolved_root = project_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise RegistryError(f"Input escapes project root: {path}") from exc


def _read_declared_input(
    project_root: Path,
    path: Path,
    spec: dict[str, Any],
    role: str,
) -> tuple[bytes, str]:
    relative = _project_relative(project_root, path)
    declared = [
        item
        for item in spec["input_artifacts"]
        if item["role"] == role and item["path"] == relative
    ]
    if len(declared) != 1:
        raise RegistryError(f"{role} {relative!r} is not uniquely preregistered")
    try:
        content = path.resolve().read_bytes()
    except OSError as exc:
        raise RegistryError(f"Cannot read {role} {path}: {exc}") from exc
    digest = _sha256_bytes(content)
    if digest != declared[0]["sha256"]:
        raise RegistryError(f"{role} hash differs from immutable spec: {relative}")
    return content, relative


def _read_frozen_code_input(
    project_root: Path,
    spec: dict[str, Any],
    role: str,
) -> tuple[bytes, str]:
    relative = str(spec[f"{role}_path"])
    path = project_root / relative
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RegistryError(f"Cannot read {role} {path}: {exc}") from exc
    if _sha256_bytes(content) != spec[f"{role}_sha256"]:
        raise RegistryError(f"Current {role} differs from immutable spec: {relative}")
    return content, relative


def _archive_artifact(
    registry: ExperimentRegistry,
    relative: str,
    content: bytes,
    role: str,
    media_type: str,
    origin_path: str | None = None,
) -> dict[str, str]:
    destination = registry.root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise RegistryError(f"Refusing to overwrite immutable run artifact: {destination}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    artifact = {
        "path": relative,
        "sha256": _sha256_bytes(content),
        "role": role,
        "media_type": media_type,
    }
    if origin_path is not None:
        artifact["origin_path"] = origin_path
    return artifact


def run_registered_diagnostic(
    project_root: Path,
    registry_root: Path,
    spec_path: Path,
    report_path: Path,
    probe_path: Path,
    actor: str,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    spec = _read_json_object(spec_path.resolve())
    validate_spec(spec)

    source_content, source_origin = _read_frozen_code_input(project_root, spec, "source")
    preset_content, preset_origin = _read_frozen_code_input(project_root, spec, "preset")
    report_content, report_origin = _read_declared_input(
        project_root, report_path, spec, "mt5-report"
    )
    probe_content, probe_origin = _read_declared_input(
        project_root, probe_path, spec, "symbol-probe"
    )

    registry = ExperimentRegistry(registry_root.resolve())
    identifiers = registry.register(spec, actor=actor)
    experiment_id = identifiers["experiment_id"]
    run_id = identifiers["run_id"]
    prefix = f"runs/{run_id}"
    started = False
    try:
        inputs = [
            _archive_artifact(
                registry,
                f"{prefix}/inputs/source.mq5",
                source_content,
                "source",
                "text/x-mql5",
                source_origin,
            ),
            _archive_artifact(
                registry,
                f"{prefix}/inputs/preset.set",
                preset_content,
                "preset",
                "text/plain",
                preset_origin,
            ),
            _archive_artifact(
                registry,
                f"{prefix}/inputs/report.htm",
                report_content,
                "mt5-report",
                "text/html",
                report_origin,
            ),
            _archive_artifact(
                registry,
                f"{prefix}/inputs/symbol_probe.json",
                probe_content,
                "symbol-probe",
                "application/json",
                probe_origin,
            ),
        ]
        registry.append(
            "STARTED",
            actor,
            experiment_id,
            run_id,
            {
                "execution_context": "offline-analysis",
                "live_trading": False,
                "input_artifacts": inputs,
            },
        )
        started = True

        archived_report = registry.root / f"{prefix}/inputs/report.htm"
        archived_probe = registry.root / f"{prefix}/inputs/symbol_probe.json"
        diagnostic = analyze_report(
            parse_report(archived_report),
            _load_probe(archived_probe),
            min_trades=int(spec["minimum_trades"]),
        )
        diagnostic_content = (
            json.dumps(
                diagnostic,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        output = _archive_artifact(
            registry,
            f"{prefix}/outputs/diagnostic.json",
            diagnostic_content,
            "diagnostic",
            "application/json",
        )
        registry.append(
            "COMPLETED",
            actor,
            experiment_id,
            run_id,
            {
                "verdict": diagnostic["verdict"],
                "technical_valid": diagnostic["technical_validity"] == "VALID",
                "exit_code": 0,
                "orders_sent": 0,
                "artifacts": [output],
            },
        )
        registry.verify()
        return {
            "valid": True,
            "experiment_id": experiment_id,
            "run_id": run_id,
            "verdict": diagnostic["verdict"],
            "technical_validity": diagnostic["technical_validity"],
            "performance_assessment": diagnostic["performance_assessment"],
            "diagnostic": output["path"],
        }
    except Exception as exc:
        if started:
            try:
                registry.append(
                    "FAILED",
                    actor,
                    experiment_id,
                    run_id,
                    {"error": str(exc), "exit_code": 2, "artifacts": []},
                )
            except RegistryError:
                pass
        else:
            try:
                registry.append(
                    "INVALIDATED",
                    actor,
                    experiment_id,
                    run_id,
                    {"reason": f"Run preparation failed: {exc}"},
                )
            except RegistryError:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registry-root", type=Path, default=Path("artifacts/experiments_v3"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--actor", default="codex")
    args = parser.parse_args()
    try:
        result = run_registered_diagnostic(
            args.project_root,
            args.registry_root,
            args.spec,
            args.report,
            args.probe,
            args.actor,
        )
    except (RegistryError, DiagnosticError, ValueError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
