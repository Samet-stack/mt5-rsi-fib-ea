#!/usr/bin/env python3
"""Build a compact, secret-averse local context packet for AI reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (
    "MQL5/Experts/RSIFibRetracementEA.mq5",
    "docs/STRATEGY_SPEC.md",
    "docs/V2_SPEC.md",
    "tests/test_strategy_math.py",
    "tests/test_source_contract.py",
)
MAX_EXCERPT_LINES = 200


def safe_project_file(raw_path: str) -> Path:
    candidate = (PROJECT_ROOT / raw_path).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {raw_path}") from exc
    if not candidate.is_file():
        raise ValueError(f"file does not exist: {raw_path}")
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def file_metadata(path: Path) -> dict[str, object]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def parse_ea_contract(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    version_match = re.search(r'^#property\s+version\s+"([^"]+)"', text, re.MULTILINE)
    inputs = []
    functions = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("input ") and not stripped.startswith("input group"):
            declaration = stripped.split("//", 1)[0].strip()
            # Compact scalar records preserve location + declaration while
            # avoiding repeated JSON object keys in token-constrained reviews.
            inputs.append(f"{line_number}:{declaration}")
        function_match = re.match(
            r"^(?:int|void|bool|double|datetime|string|ulong|ENUM_[A-Z0-9_]+)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            stripped,
        )
        if function_match:
            functions.append(f"{line_number}:{function_match.group(1)}")
    return {
        "version": version_match.group(1) if version_match else "unknown",
        "inputs": inputs,
        "functions": functions,
    }


def discover_tests() -> list[dict[str, object]]:
    tests = []
    for path in sorted((PROJECT_ROOT / "tests").glob("test_*.py")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = re.match(r"\s+def\s+(test_[A-Za-z0-9_]+)\s*\(", line)
            if match:
                tests.append({"file": relative(path), "line": line_number, "name": match.group(1)})
    return tests


def parse_excerpt(spec: str) -> dict[str, object]:
    parts = spec.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError(f"invalid excerpt, expected FILE:START:END: {spec}")
    raw_path, raw_start, raw_end = parts
    start = int(raw_start)
    end = int(raw_end)
    if start < 1 or end < start or end - start + 1 > MAX_EXCERPT_LINES:
        raise ValueError(f"excerpt must contain 1..{MAX_EXCERPT_LINES} lines: {spec}")
    path = safe_project_file(raw_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if start > len(lines):
        raise ValueError(f"excerpt starts after EOF: {spec}")
    end = min(end, len(lines))
    content = "\n".join(f"{index}: {lines[index - 1]}" for index in range(start, end + 1))
    return {"path": relative(path), "start": start, "end": end, "content": content}


def build_manifest(files: list[str], excerpts: list[str]) -> dict[str, object]:
    selected = []
    seen = set()
    for raw_path in files:
        path = safe_project_file(raw_path)
        rel = relative(path)
        if rel not in seen:
            selected.append(file_metadata(path))
            seen.add(rel)

    ea_path = safe_project_file("MQL5/Experts/RSIFibRetracementEA.mq5")
    return {
        "schema": "rsifib-ai-context/v1",
        "project": PROJECT_ROOT.name,
        "files": selected,
        "ea_contract": parse_ea_contract(ea_path),
        "tests": discover_tests(),
        "excerpts": [parse_excerpt(item) for item in excerpts],
        "invariants": [
            "demo-only default",
            "no martingale/grid/averaging-down",
            "no market fallback for entries",
            "closed-bar RSI signals",
            "V1 ratios remain configurable",
            "all strategy-changing V2 modules default off",
            "ambiguous broker exposure enters STATE_FAULT",
            "original strategy SL remains separate from live break-even SL",
            "OnTradeTransaction only invalidates runtime caches",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", action="append", default=[], help="Project-relative file to hash")
    parser.add_argument("--excerpt", action="append", default=[], help="Bounded FILE:START:END excerpt")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    try:
        files = args.file or list(DEFAULT_FILES)
        manifest = build_manifest(files, args.excerpt)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.pretty:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
