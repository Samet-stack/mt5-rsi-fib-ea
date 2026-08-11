#!/usr/bin/env python3
"""Tests for the immutable V4 MT5 run archiver."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from tools.archive_mt5_run import (
    ArchiveError,
    archive_mt5_run,
    compare_effective_parameters,
    parse_preset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestArchiveMT5Run(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "expert.mq5"
        self.preset = self.directory / "candidate.set"
        self.report = self.directory / "report.htm"
        self.ex5 = self.directory / "expert.ex5"
        self.log = self.directory / "tester.log"
        self.effective = self.directory / "effective.json"
        self.calendar_data = self.directory / "news_events.csv"
        self.source.write_bytes(b"// frozen source\n")
        self.preset.write_text(
            "; test preset\n"
            "InpDemoOnly=true\n"
            "InpRiskPercent=0.50\n"
            'InpNewsCurrency="USD"\n'
            "InpMode=CALENDAR_IMPORTANCE_HIGH\n",
            encoding="utf-8",
        )
        self.report.write_bytes(b"<html><body>tester report</body></html>\n")
        self.ex5.write_bytes(b"EX5-binary")
        self.log.write_text("tester complete\n", encoding="utf-8")
        self.calendar_data.write_text(
            "schema;RSIFIB_NEWS_V1;;\n"
            "timezone;BROKER_SERVER;;\n"
            "coverage_from;2026.01.01 00:00;;\n"
            "coverage_to;2026.02.01 00:00;;\n"
            "server_time;currency;importance;name\n",
            encoding="utf-8",
        )
        self.effective.write_text(
            json.dumps(
                {
                    "inputs": {
                        "InpDemoOnly": True,
                        "InpRiskPercent": "0.5000",
                        "InpNewsCurrency": "USD",
                        "InpMode": "CALENDAR_IMPORTANCE_HIGH",
                    }
                }
            ),
            encoding="utf-8",
        )

    def archive(self, run_id: str | None = None, **overrides):
        arguments = {
            "root": self.directory / "registry",
            "run_id": run_id or str(uuid.uuid4()),
            "source": self.source,
            "preset": self.preset,
            "report": self.report,
            "ex5": self.ex5,
            "log": self.log,
            "effective_parameters": self.effective,
            "from_date": "2026-01-01",
            "to_date": "2026-02-01",
            "broker": "MetaQuotes Ltd.",
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "terminal_build": 6090,
            "model": "Every tick based on real ticks",
            "round_turn_cost_per_lot": "7.00",
            "cost_currency": "USD",
            "cost_verified": True,
            "seed": 20260811,
        }
        arguments.update(overrides)
        return archive_mt5_run(**arguments)

    def test_archives_required_and_optional_files_with_hashes(self):
        run_id = str(uuid.uuid4())
        manifest = self.archive(run_id)
        run_directory = self.directory / "registry" / "runs" / run_id
        stored = json.loads((run_directory / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(stored, manifest)
        self.assertEqual(stored["schema"], "rsifib-mt5-run-archive/v1")
        self.assertEqual(stored["window"], {"from": "2026-01-01", "to": "2026-02-01"})
        self.assertEqual(stored["environment"]["terminal_build"], 6090)
        self.assertEqual(stored["cost"]["round_turn_per_lot"], "7")
        self.assertTrue(stored["parameter_comparison"]["matched"])
        self.assertNotIn(str(self.directory), json.dumps(stored))

        by_role = {artifact["role"]: artifact for artifact in stored["artifacts"]}
        self.assertEqual(
            set(by_role),
            {
                "source",
                "preset",
                "compiled-binary",
                "mt5-report",
                "tester-log",
                "effective-parameters",
            },
        )
        for artifact in stored["artifacts"]:
            content = (run_directory / artifact["path"]).read_bytes()
            self.assertEqual(artifact["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(artifact["bytes"], len(content))

    def test_manifest_bytes_are_deterministic_across_archive_roots(self):
        run_id = str(uuid.uuid4())
        first = self.archive(run_id, root=self.directory / "one")
        first_bytes = (
            self.directory / "one" / "runs" / run_id / "manifest.json"
        ).read_bytes()
        second = self.archive(run_id, root=self.directory / "two")
        second_bytes = (
            self.directory / "two" / "runs" / run_id / "manifest.json"
        ).read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_bytes)

    def test_archives_exact_calendar_input_when_supplied(self):
        run_id = str(uuid.uuid4())
        manifest = self.archive(run_id, calendar_data=self.calendar_data)
        run_directory = self.directory / "registry" / "runs" / run_id
        by_role = {artifact["role"]: artifact for artifact in manifest["artifacts"]}

        self.assertIn("calendar-data", by_role)
        artifact = by_role["calendar-data"]
        self.assertEqual(artifact["path"], "inputs/news_events.csv")
        archived = (run_directory / artifact["path"]).read_bytes()
        self.assertEqual(archived, self.calendar_data.read_bytes())
        self.assertEqual(artifact["sha256"], hashlib.sha256(archived).hexdigest())

    def test_existing_run_directory_is_never_overwritten(self):
        run_id = str(uuid.uuid4())
        self.archive(run_id)
        manifest_path = self.directory / "registry" / "runs" / run_id / "manifest.json"
        original = manifest_path.read_bytes()

        with self.assertRaisesRegex(ArchiveError, "refusing to overwrite"):
            self.archive(run_id)

        self.assertEqual(manifest_path.read_bytes(), original)

    def test_missing_source_preset_or_report_is_rejected_before_directory_creation(self):
        missing = self.directory / "missing.file"
        cases = (("source", missing), ("preset", missing), ("report", missing))
        for field, value in cases:
            with self.subTest(field=field):
                root = self.directory / f"registry-{field}"
                with self.assertRaisesRegex(ArchiveError, "missing"):
                    self.archive(root=root, **{field: value})
                self.assertFalse((root / "runs").exists())

    def test_parameter_mismatch_is_rejected_before_directory_creation(self):
        self.effective.write_text(
            json.dumps(
                {
                    "InpDemoOnly": True,
                    "InpRiskPercent": 4.0,
                    "InpNewsCurrency": "USD",
                    "InpMode": "CALENDAR_IMPORTANCE_HIGH",
                }
            ),
            encoding="utf-8",
        )
        root = self.directory / "mismatch-registry"
        with self.assertRaisesRegex(ArchiveError, "do not match frozen preset"):
            self.archive(root=root)
        self.assertFalse((root / "runs").exists())

    def test_parameter_comparison_reports_missing_unexpected_and_changed(self):
        comparison = compare_effective_parameters(
            {"InpA": "true", "InpB": "1.00", "InpC": '"USD"'},
            {"InpA": False, "InpB": 1, "InpD": "extra"},
        )
        self.assertFalse(comparison["matched"])
        self.assertEqual(comparison["missing"], ["InpC"])
        self.assertEqual(comparison["unexpected"], ["InpD"])
        self.assertEqual(comparison["mismatched"][0]["name"], "InpA")

    def test_preset_optimization_form_uses_active_value_and_rejects_duplicates(self):
        self.preset.write_text("InpRisk=0.25||0.10||0.05||0.50||Y\n", encoding="utf-8")
        self.assertEqual(parse_preset(self.preset), {"InpRisk": "0.25"})
        self.preset.write_text("InpRisk=0.25\nInpRisk=0.50\n", encoding="utf-8")
        with self.assertRaisesRegex(ArchiveError, "duplicate"):
            parse_preset(self.preset)

    def test_cli_runs_on_linux_and_prints_machine_readable_manifest(self):
        run_id = str(uuid.uuid4())
        root = self.directory / "cli-registry"
        completed = subprocess.run(
            [
                sys.executable,
                "tools/archive_mt5_run.py",
                "--root",
                str(root),
                "--run-id",
                run_id,
                "--source",
                str(self.source),
                "--preset",
                str(self.preset),
                "--report",
                str(self.report),
                "--from-date",
                "2026-01-01",
                "--to-date",
                "2026-02-01",
                "--broker",
                "MetaQuotes Ltd.",
                "--symbol",
                "XAUUSD",
                "--timeframe",
                "M15",
                "--terminal-build",
                "6090",
                "--model",
                "Every tick based on real ticks",
                "--round-turn-cost-per-lot",
                "7.00",
                "--cost-verified",
                "--seed",
                "20260811",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = json.loads(completed.stdout)
        self.assertEqual(manifest["run_id"], run_id)
        self.assertTrue((root / "runs" / run_id / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
