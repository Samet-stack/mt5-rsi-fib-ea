#!/usr/bin/env python3
"""Public-repository safety and reproducibility contracts."""

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestPublicationHygiene(unittest.TestCase):
    def test_every_public_preset_keeps_cost_gate_closed(self):
        presets = sorted((PROJECT_ROOT / "presets").glob("*.set"))
        self.assertTrue(presets)
        for preset in presets:
            with self.subTest(preset=preset.name):
                text = preset.read_text(encoding="utf-8")
                self.assertIn("InpCostModelVerified=false", text)
                self.assertNotIn("InpCostModelVerified=true", text)

    def test_current_sources_do_not_embed_personal_machine_paths(self):
        roots = [
            PROJECT_ROOT / "MQL5",
            PROJECT_ROOT / "docs",
            PROJECT_ROOT / "presets",
            PROJECT_ROOT / "tests",
            PROJECT_ROOT / "tools",
        ]
        files = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "CONTRIBUTING.md"]
        for root in roots:
            files.extend(path for path in root.rglob("*") if path.is_file())

        forbidden = (
            "/home/" + "9lx7",
            "/mnt/c/Users/" + "samet",
            "C:\\Users\\" + "samet",
            "D0E8209F77C8CF37" + "AD8BF550E51FF075",
        )
        for path in files:
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                with self.subTest(path=path.relative_to(PROJECT_ROOT), token=token):
                    self.assertNotIn(token, text)

    def test_no_obvious_secret_material_is_committed_in_current_sources(self):
        pattern = re.compile(
            r"BEGIN (?:RSA|OPENSSH|EC|PGP) PRIVATE KEY|"
            r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|"
            r"sk-[A-Za-z0-9]{20,}"
        )
        for directory in ("MQL5", "docs", "presets", "tests", "tools"):
            for path in (PROJECT_ROOT / directory).rglob("*"):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                with self.subTest(path=path.relative_to(PROJECT_ROOT)):
                    self.assertIsNone(pattern.search(text))

    def test_public_archives_do_not_embed_local_paths_or_account_identity(self):
        run_roots = [
            PROJECT_ROOT / "artifacts" / "experiments_v4" / "runs",
            PROJECT_ROOT / "artifacts" / "experiments_v4_5" / "runs",
        ]
        for runs in run_roots:
            self.assertTrue(runs.is_dir())
        forbidden = (
            "/home/" + "9lx7",
            "/mnt/c/Users/" + "samet",
            "C:\\Users\\" + "samet",
            "D0E8209F77C8CF37" + "AD8BF550E51FF075",
            "ACCOUNT_LOGIN",
            "ACCOUNT_NAME",
        )
        for runs in run_roots:
            for path in runs.rglob("*"):
                if not path.is_file() or path.suffix.lower() == ".ex5":
                    continue
                content = path.read_bytes()
                text = None
                for encoding in ("utf-8-sig", "utf-16", "cp1252"):
                    try:
                        text = content.decode(encoding)
                        break
                    except UnicodeError:
                        continue
                self.assertIsNotNone(text, path)
                for token in forbidden:
                    with self.subTest(path=path.relative_to(PROJECT_ROOT), token=token):
                        self.assertNotIn(token, text)

    def test_public_governance_and_validation_disclaimer_exist(self):
        for relative in (
            "CONTRIBUTING.md",
            "SECURITY.md",
            "docs/ROADMAP.md",
            ".github/workflows/ci.yml",
        ):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)

        report = (PROJECT_ROOT / "RAPPORT_AMELIORATIONS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("performance non vérifiée", report.lower())
        self.assertIn("aucun rapport brut", report.lower())


if __name__ == "__main__":
    unittest.main()
