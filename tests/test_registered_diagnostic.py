#!/usr/bin/env python3
"""End-to-end test for preregistered offline diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.experiment_registry import ExperimentRegistry, RegistryError
from tools.run_registered_diagnostic import run_registered_diagnostic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = PROJECT_ROOT / "experiments" / "AUDIT_V3_INFRA_SPEC.json"
PROBE = (
    PROJECT_ROOT
    / "artifacts"
    / "symbol-probe-2026-08-05"
    / "XAUUSD_MetaQuotes-Demo.json"
)
IS_REPORT = (
    PROJECT_ROOT
    / "artifacts"
    / "validation-2026-08-04"
    / "RSIFibEA_IS_202602_202605_RSIFibEA_xau_stop039_be0_010.htm"
)


def historical_replay_spec(directory: Path) -> Path:
    """Point the old report at the exact archived source/preset that produced it."""

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    archived_prefix = (
        PROJECT_ROOT
        / "artifacts"
        / "experiments_v3"
        / "runs"
        / "98c7d463-751b-41a4-8869-cb75a26a003e"
        / "inputs"
    )
    spec["source_path"] = (archived_prefix / "source.mq5").relative_to(PROJECT_ROOT).as_posix()
    spec["preset_path"] = (archived_prefix / "preset.set").relative_to(PROJECT_ROOT).as_posix()
    path = directory / "historical-replay-spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


class TestRegisteredDiagnostic(unittest.TestCase):
    def test_archives_inputs_and_links_diagnostic_to_immutable_spec(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            registry_root = temp_root / "registry"
            replay_spec = historical_replay_spec(temp_root)
            result = run_registered_diagnostic(
                PROJECT_ROOT,
                registry_root,
                replay_spec,
                IS_REPORT,
                PROBE,
                "test-harness",
            )
            events = ExperimentRegistry(registry_root).verify()
            diagnostic = json.loads(
                (registry_root / result["diagnostic"]).read_text(encoding="utf-8")
            )

            self.assertEqual([event["type"] for event in events], ["REGISTERED", "STARTED", "COMPLETED"])
            self.assertEqual(result["verdict"], "INVALID_TECHNICAL")
            self.assertEqual(diagnostic["policy"]["minimum_trades"], 100)
            self.assertEqual(diagnostic["provenance"]["server"], "MetaQuotes-Demo")
            self.assertEqual(events[-1]["payload"]["orders_sent"], 0)

    def test_unregistered_report_is_rejected_before_run_creation(self):
        unregistered = (
            PROJECT_ROOT
            / "artifacts"
            / "validation-2026-08-04"
            / "RSIFibEA_smoke_XAUUSD_M15.htm"
        )
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            registry_root = temp_root / "registry"
            replay_spec = historical_replay_spec(temp_root)
            with self.assertRaisesRegex(RegistryError, "not uniquely preregistered"):
                run_registered_diagnostic(
                    PROJECT_ROOT,
                    registry_root,
                    replay_spec,
                    unregistered,
                    PROBE,
                    "test-harness",
                )
            self.assertFalse(registry_root.exists())


if __name__ == "__main__":
    unittest.main()
