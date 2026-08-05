#!/usr/bin/env python3

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "ai_context_manifest.py"


class TestAIContextManifest(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_manifest_is_compact_and_structured(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "rsifib-ai-context/v1")
        self.assertEqual(payload["project"], "mt5-rsi-fib-ea")
        self.assertTrue(payload["ea_contract"]["inputs"])
        self.assertTrue(payload["ea_contract"]["functions"])
        self.assertTrue(payload["tests"])
        self.assertLess(len(result.stdout), 30000)

    def test_excerpt_is_numbered_and_bounded(self):
        result = self.run_tool("--excerpt", "README.md:1:3")
        self.assertEqual(result.returncode, 0, result.stderr)
        excerpt = json.loads(result.stdout)["excerpts"][0]
        self.assertEqual(excerpt["start"], 1)
        self.assertEqual(excerpt["end"], 3)
        self.assertIn("1: # RSI Fibonacci", excerpt["content"])

    def test_path_escape_is_rejected(self):
        result = self.run_tool("--file", "../AGENTS.md")
        self.assertEqual(result.returncode, 2)
        self.assertIn("escapes project root", result.stderr)

    def test_oversized_excerpt_is_rejected(self):
        result = self.run_tool("--excerpt", "README.md:1:201")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must contain", result.stderr)


if __name__ == "__main__":
    unittest.main()
