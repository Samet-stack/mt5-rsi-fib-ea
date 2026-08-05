#!/usr/bin/env python3
"""Tests for the append-only, tamper-evident experiment registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from tools.experiment_registry import (
    ExperimentRegistry,
    RegistryError,
    SPEC_SCHEMA,
    canonical_json,
    sha256_json,
)

SOURCE_CONTENT = b"frozen source\n"
PRESET_CONTENT = b"frozen preset\n"
COMPILED_CONTENT = b"EX5-test-binary"
REPORT_CONTENT = b"<html><body>MT5 report</body></html>\n"
PROBE_CONTENT = json.dumps(
    {
        "schema": "rsifib-mt5-symbol-probe/v1",
        "tester_only": True,
        "orders_sent": 0,
    }
).encode()
SOURCE_HASH = hashlib.sha256(SOURCE_CONTENT).hexdigest()
PRESET_HASH = hashlib.sha256(PRESET_CONTENT).hexdigest()


def sample_spec() -> dict[str, object]:
    return {
        "schema": SPEC_SCHEMA,
        "hypothesis_id": "AUDIT-V3",
        "hypothesis": "Infrastructure audit only; no strategy optimization",
        "phase": "audit",
        "single_change": "Verify the V3 research infrastructure without changing strategy logic",
        "planned_ranges": {"strategy_parameters": "none"},
        "total_variants": 1,
        "data": {
            "broker": "MetaQuotes Ltd.",
            "server": "MetaQuotes-Demo",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "role": "contaminated-development-only",
            "currency": "USD",
            "deposit": 3000.0,
            "leverage": "1:100",
            "terminal_build": 6090,
            "windows": [
                {
                    "start": "2026-02-01",
                    "end": "2026-07-01",
                    "role": "contaminated-development-only",
                }
            ],
        },
        "primary_metric": "infrastructure_verification",
        "acceptance_criteria": ["All declared tests pass"],
        "rejection_criteria": ["Any live-trading path is enabled"],
        "source_sha256": SOURCE_HASH,
        "source_path": "MQL5/Experts/RSIFibRetracementEA.mq5",
        "preset_sha256": PRESET_HASH,
        "preset_path": "presets/example.set",
        "seed": 20260805,
        "minimum_trades": 100,
        "safety": {"demo_only": True, "live_trading": False},
        "input_artifacts": [
            {
                "role": "mt5-report",
                "path": "artifacts/report.htm",
                "sha256": hashlib.sha256(REPORT_CONTENT).hexdigest(),
                "window": {
                    "start": "2026-02-01",
                    "end": "2026-07-01",
                    "role": "contaminated-development-only",
                },
            },
            {
                "role": "symbol-probe",
                "path": "artifacts/probe.json",
                "sha256": hashlib.sha256(PROBE_CONTENT).hexdigest(),
            },
        ],
    }


def artifact_ref(
    registry: ExperimentRegistry,
    name: str,
    content: bytes,
    role: str,
    media_type: str,
    origin_path: str | None = None,
) -> dict[str, str]:
    path = registry.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    result = {
        "path": name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
        "media_type": media_type,
    }
    if origin_path is not None:
        result["origin_path"] = origin_path
    return result


def frozen_inputs(
    registry: ExperimentRegistry,
    prefix: str = "runs",
    context: str = "offline-analysis",
) -> list[dict[str, str]]:
    inputs = [
        artifact_ref(
            registry,
            f"{prefix}/source.mq5",
            SOURCE_CONTENT,
            "source",
            "text/x-mql5",
            "MQL5/Experts/RSIFibRetracementEA.mq5",
        ),
        artifact_ref(
            registry,
            f"{prefix}/preset.set",
            PRESET_CONTENT,
            "preset",
            "text/plain",
            "presets/example.set",
        ),
    ]
    if context in {"static-audit", "tester"}:
        inputs.append(
            artifact_ref(
                registry,
                f"{prefix}/expert.ex5",
                COMPILED_CONTENT,
                "compiled-binary",
                "application/octet-stream",
                "MQL5/Experts/example.ex5",
            )
        )
    if context == "offline-analysis":
        inputs.extend(
            [
                artifact_ref(
                    registry,
                    f"{prefix}/report.htm",
                    REPORT_CONTENT,
                    "mt5-report",
                    "text/html",
                    "artifacts/report.htm",
                ),
                artifact_ref(
                    registry,
                    f"{prefix}/probe.json",
                    PROBE_CONTENT,
                    "symbol-probe",
                    "application/json",
                    "artifacts/probe.json",
                ),
            ]
        )
    elif context == "tester":
        inputs.append(
            artifact_ref(
                registry,
                f"{prefix}/probe.json",
                PROBE_CONTENT,
                "symbol-probe",
                "application/json",
                "artifacts/probe.json",
            )
        )
    return inputs


class TestExperimentRegistry(unittest.TestCase):
    def test_canonical_hash_is_order_independent(self):
        left = {"b": 2, "a": {"y": 1, "x": 0}}
        right = {"a": {"x": 0, "y": 1}, "b": 2}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(sha256_json(left), sha256_json(right))

    def test_register_start_complete_and_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            identifiers = registry.register(sample_spec(), actor="codex")
            inputs = frozen_inputs(registry, context="static-audit")
            registry.append(
                "STARTED",
                "harness",
                identifiers["experiment_id"],
                identifiers["run_id"],
                {
                    "execution_context": "static-audit",
                    "live_trading": False,
                    "input_artifacts": inputs,
                },
            )
            result_content = json.dumps(
                {
                    "schema": "rsifib-audit-result/v1",
                    "verdict": "INFRASTRUCTURE_COMPLETE",
                }
            ).encode()
            result = artifact_ref(
                registry,
                "runs/result.json",
                result_content,
                "audit-result",
                "application/json",
            )
            registry.append(
                "COMPLETED",
                "harness",
                identifiers["experiment_id"],
                identifiers["run_id"],
                {
                    "verdict": "INFRASTRUCTURE_COMPLETE",
                    "technical_valid": True,
                    "exit_code": 0,
                    "orders_sent": 0,
                    "artifacts": [result],
                    "checks": {"tests": 72},
                },
            )
            events = registry.verify()

            self.assertEqual([event["seq"] for event in events], [1, 2, 3])
            self.assertEqual(events[2]["payload"]["orders_sent"], 0)
            spec_path = registry.specs_dir / f"{identifiers['experiment_id']}.json"
            self.assertTrue(spec_path.is_file())

    def test_identical_specs_share_experiment_but_not_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            first = registry.register(sample_spec(), actor="codex")
            second = registry.register(sample_spec(), actor="gemini")
            self.assertEqual(first["experiment_id"], second["experiment_id"])
            self.assertNotEqual(first["run_id"], second["run_id"])
            self.assertEqual(len(list(registry.specs_dir.glob("*.json"))), 1)

    def test_invalid_transition_is_rejected_without_append(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            identifiers = registry.register(sample_spec(), actor="codex")
            with self.assertRaises(RegistryError):
                registry.append(
                    "COMPLETED",
                    "harness",
                    identifiers["experiment_id"],
                    identifiers["run_id"],
                )
            self.assertEqual(len(registry.verify()), 1)

    def test_tampered_event_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            registry.register(sample_spec(), actor="codex")
            line = json.loads(registry.ledger_path.read_text(encoding="utf-8"))
            line["payload"]["spec"] = "specs/forged.json"
            registry.ledger_path.write_text(
                json.dumps(line, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RegistryError, "Tampered event"):
                registry.verify()

    def test_corrupted_immutable_spec_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            identifiers = registry.register(sample_spec(), actor="codex")
            spec_path = registry.specs_dir / f"{identifiers['experiment_id']}.json"
            corrupted = sample_spec()
            corrupted["hypothesis"] = "changed after registration"
            spec_path.write_text(json.dumps(corrupted), encoding="utf-8")
            with self.assertRaisesRegex(RegistryError, "Spec hash mismatch"):
                registry.verify()

    def test_run_id_must_be_canonical_uuid(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            upper = str(uuid.uuid4()).upper()
            with self.assertRaisesRegex(RegistryError, "canonical lowercase"):
                registry.register(sample_spec(), actor="codex", run_id=upper)

    def test_under_specified_research_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            spec = sample_spec()
            del spec["primary_metric"]
            with self.assertRaisesRegex(RegistryError, "primary_metric"):
                registry.register(spec, actor="codex")

    def test_live_trading_spec_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            spec = sample_spec()
            spec["safety"] = {"demo_only": True, "live_trading": True}
            with self.assertRaisesRegex(RegistryError, "demo_only=true"):
                registry.register(spec, actor="codex")

    def test_reversed_or_overlapping_windows_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            spec = sample_spec()
            spec["data"]["windows"] = [
                {
                    "start": "2026-07-01",
                    "end": "2026-05-01",
                    "role": "opened-contaminated-OOS",
                }
            ]
            with self.assertRaisesRegex(RegistryError, "start < end"):
                registry.register(spec, actor="codex")

    def test_minimum_trade_policy_cannot_be_preregistered_below_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            spec = sample_spec()
            spec["minimum_trades"] = 3
            with self.assertRaisesRegex(RegistryError, "at least 100"):
                registry.register(spec, actor="codex")

    def test_empty_completed_payload_cannot_claim_success(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            identifiers = registry.register(sample_spec(), actor="codex")
            inputs = frozen_inputs(registry)
            registry.append(
                "STARTED",
                "harness",
                identifiers["experiment_id"],
                identifiers["run_id"],
                {
                    "execution_context": "offline-analysis",
                    "live_trading": False,
                    "input_artifacts": inputs,
                },
            )
            with self.assertRaisesRegex(RegistryError, "invalid verdict"):
                registry.append(
                    "COMPLETED",
                    "harness",
                    identifiers["experiment_id"],
                    identifiers["run_id"],
                    {},
                )

    def test_changed_registered_artifact_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ExperimentRegistry(Path(directory))
            identifiers = registry.register(sample_spec(), actor="codex")
            inputs = frozen_inputs(registry)
            registry.append(
                "STARTED",
                "harness",
                identifiers["experiment_id"],
                identifiers["run_id"],
                {
                    "execution_context": "offline-analysis",
                    "live_trading": False,
                    "input_artifacts": inputs,
                },
            )
            (registry.root / "runs/source.mq5").write_bytes(b"changed")
            with self.assertRaisesRegex(RegistryError, "artifact hash mismatch"):
                registry.verify()


if __name__ == "__main__":
    unittest.main()
