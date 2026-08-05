#!/usr/bin/env python3
"""Tamper-evident, append-only experiment registry for RSI Fib research.

The registry deliberately stores every run, including failures and invalidations.
It is dependency-free and intended to run from WSL.  Strategy results must never
be edited in place: corrections are represented by later events.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Iterator
import uuid


SCHEMA = "rsifib-ledger-event/v1"
SPEC_SCHEMA = "rsifib-experiment-spec/v1"
GENESIS_HASH = "0" * 64
EVENT_TYPES = {
    "REGISTERED",
    "STARTED",
    "COMPLETED",
    "FAILED",
    "INVALIDATED",
    "REPARSED",
    "DECISION",
}
VERDICTS = {
    "INVALID_TECHNICAL",
    "REJECTED",
    "INCONCLUSIVE",
    "ELIGIBLE_FOR_NEXT_GATE",
    "INFRASTRUCTURE_COMPLETE",
    "GATE_BLOCKED",
    "NO_DECISION",
}
PHASES = {"audit", "diagnostic", "development", "validation", "walk-forward", "holdout", "forward-demo"}
DATA_ROLES = {
    "contaminated-development-only",
    "contaminated-development-IS",
    "opened-contaminated-OOS",
    "walk-forward-train",
    "walk-forward-validation",
    "final-holdout",
    "demo-forward",
}
ARTIFACT_ROLES = {
    "source",
    "preset",
    "compiled-binary",
    "mt5-report",
    "symbol-probe",
    "diagnostic",
    "audit-result",
    "test-log",
}
ARTIFACT_MEDIA_TYPES = {
    "source": {"text/x-mql5", "text/plain"},
    "preset": {"text/plain"},
    "compiled-binary": {"application/octet-stream"},
    "mt5-report": {"text/html"},
    "symbol-probe": {"application/json"},
    "diagnostic": {"application/json"},
    "audit-result": {"application/json"},
    "test-log": {"text/plain", "application/json"},
}
ACTOR_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,96}$")


class RegistryError(RuntimeError):
    """Raised when the ledger, a transition, or an immutable artifact is invalid."""


def canonical_json(value: Any) -> str:
    """Return the only JSON representation used for IDs and event hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RegistryError(f"Expected a JSON object in {path}")
    return value


def _validate_identifier(name: str, value: str) -> None:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise RegistryError(f"{name} must be a UUID: {value!r}") from exc
    if str(parsed) != value:
        raise RegistryError(f"{name} must use canonical lowercase UUID form")


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"Spec field {field!r} must be a non-empty string")
    return value


def _string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise RegistryError(f"Spec field {field!r} must be a non-empty list")
    for item in value:
        _non_empty_string(item, field)


def _safe_relative_path(value: Any, field: str) -> str:
    path_text = _non_empty_string(value, field)
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise RegistryError(f"Spec field {field!r} must be a safe relative path")
    return path_text


def validate_spec(spec: dict[str, Any]) -> None:
    """Reject under-specified research before it can enter the ledger."""

    if spec.get("schema") != SPEC_SCHEMA:
        raise RegistryError(f"Spec schema must be {SPEC_SCHEMA!r}")

    hypothesis_id = _non_empty_string(spec.get("hypothesis_id"), "hypothesis_id")
    if not IDENTIFIER_PATTERN.fullmatch(hypothesis_id):
        raise RegistryError("Spec hypothesis_id contains unsupported characters")
    for field in ("hypothesis", "phase", "single_change", "primary_metric"):
        _non_empty_string(spec.get(field), field)
    if spec.get("phase") not in PHASES:
        raise RegistryError(f"Spec phase must be one of {sorted(PHASES)}")

    planned_ranges = spec.get("planned_ranges")
    if not isinstance(planned_ranges, dict) or not planned_ranges:
        raise RegistryError("Spec planned_ranges must be a non-empty object")
    total_variants = spec.get("total_variants")
    if (
        not isinstance(total_variants, int)
        or isinstance(total_variants, bool)
        or not 1 <= total_variants <= 100_000
    ):
        raise RegistryError("Spec total_variants must be an integer from 1 to 100000")

    data = spec.get("data")
    if not isinstance(data, dict):
        raise RegistryError("Spec data must be an object")
    for field in ("broker", "server", "symbol", "timeframe", "role", "currency", "leverage"):
        _non_empty_string(data.get(field), f"data.{field}")
    if data.get("role") not in DATA_ROLES:
        raise RegistryError(f"Spec data.role must be one of {sorted(DATA_ROLES)}")
    deposit = data.get("deposit")
    if (
        not isinstance(deposit, (int, float))
        or isinstance(deposit, bool)
        or not math.isfinite(float(deposit))
        or float(deposit) <= 0.0
    ):
        raise RegistryError("Spec data.deposit must be a positive finite number")
    terminal_build = data.get("terminal_build")
    if (
        not isinstance(terminal_build, int)
        or isinstance(terminal_build, bool)
        or terminal_build <= 0
    ):
        raise RegistryError("Spec data.terminal_build must be a positive integer")
    windows = data.get("windows")
    if not isinstance(windows, list) or not windows:
        raise RegistryError("Spec data.windows must be a non-empty list")
    previous_end: date | None = None
    for index, window in enumerate(windows):
        if not isinstance(window, dict):
            raise RegistryError(f"Spec data.windows[{index}] must be an object")
        for field in ("start", "end", "role"):
            _non_empty_string(window.get(field), f"data.windows[{index}].{field}")
        if window["role"] not in DATA_ROLES:
            raise RegistryError(
                f"Spec data.windows[{index}].role must be one of {sorted(DATA_ROLES)}"
            )
        try:
            start = date.fromisoformat(window["start"])
            end = date.fromisoformat(window["end"])
        except ValueError as exc:
            raise RegistryError(
                f"Spec data.windows[{index}] dates must be canonical ISO dates"
            ) from exc
        if start.isoformat() != window["start"] or end.isoformat() != window["end"]:
            raise RegistryError(
                f"Spec data.windows[{index}] dates must be canonical ISO dates"
            )
        if start >= end:
            raise RegistryError(f"Spec data.windows[{index}] must have start < end")
        if previous_end is not None and start < previous_end:
            raise RegistryError("Spec data.windows must be chronological and non-overlapping")
        previous_end = end

    _string_list(spec.get("acceptance_criteria"), "acceptance_criteria")
    _string_list(spec.get("rejection_criteria"), "rejection_criteria")
    for field in ("source_sha256", "preset_sha256"):
        value = spec.get(field)
        if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
            raise RegistryError(f"Spec {field} must be a lowercase SHA-256 hash")
    _safe_relative_path(spec.get("source_path"), "source_path")
    _safe_relative_path(spec.get("preset_path"), "preset_path")
    seed = spec.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise RegistryError("Spec seed must be a non-negative integer")
    minimum_trades = spec.get("minimum_trades")
    if (
        not isinstance(minimum_trades, int)
        or isinstance(minimum_trades, bool)
        or minimum_trades < 100
    ):
        raise RegistryError("Spec minimum_trades must be an integer of at least 100")

    safety = spec.get("safety")
    if not isinstance(safety, dict):
        raise RegistryError("Spec safety must be an object")
    if safety.get("demo_only") is not True or safety.get("live_trading") is not False:
        raise RegistryError("Spec safety must enforce demo_only=true and live_trading=false")

    inputs = spec.get("input_artifacts")
    if not isinstance(inputs, list) or not inputs:
        raise RegistryError("Spec input_artifacts must be a non-empty list")
    input_paths: set[str] = set()
    report_windows: list[dict[str, str]] = []
    probe_count = 0
    for item in inputs:
        if not isinstance(item, dict):
            raise RegistryError("Spec input_artifacts entries must be objects")
        role = item.get("role")
        if role not in {"mt5-report", "symbol-probe"}:
            raise RegistryError("Spec input_artifacts role must be mt5-report or symbol-probe")
        path = _safe_relative_path(item.get("path"), "input_artifacts.path")
        if path in input_paths:
            raise RegistryError("Spec input_artifacts paths must be unique")
        input_paths.add(path)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise RegistryError("Spec input_artifacts sha256 is invalid")
        if role == "symbol-probe":
            probe_count += 1
            if "window" in item:
                raise RegistryError("Spec symbol-probe input must not declare a window")
        else:
            window = item.get("window")
            if not isinstance(window, dict):
                raise RegistryError("Spec mt5-report input requires a window")
            report_windows.append(window)
    if probe_count != 1:
        raise RegistryError("Spec input_artifacts require exactly one symbol-probe")
    if report_windows != windows:
        raise RegistryError(
            "Spec mt5-report input windows must exactly match data.windows in order"
        )


def _validate_artifact_list(value: Any, field: str, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise RegistryError(f"Event payload {field} must be a non-empty artifact list")
    seen: set[str] = set()
    for artifact in value:
        if not isinstance(artifact, dict):
            raise RegistryError(f"Event payload {field} contains a non-object artifact")
        path = artifact.get("path")
        digest = artifact.get("sha256")
        role = artifact.get("role")
        media_type = artifact.get("media_type")
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"Event payload {field} artifact path is invalid")
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts or path in seen:
            raise RegistryError(f"Event payload {field} artifact path is unsafe or duplicate")
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise RegistryError(f"Event payload {field} artifact hash is invalid")
        if role not in ARTIFACT_ROLES:
            raise RegistryError(f"Event payload {field} artifact role is invalid")
        if media_type not in ARTIFACT_MEDIA_TYPES[role]:
            raise RegistryError(
                f"Event payload {field} media_type is invalid for role {role!r}"
            )
        if field == "input_artifacts" or role in {"source", "preset"}:
            origin = artifact.get("origin_path")
            if not isinstance(origin, str) or not origin.strip():
                raise RegistryError(
                    f"Event payload {field} {role} requires origin_path"
                )
            origin_path = Path(origin)
            if origin_path.is_absolute() or ".." in origin_path.parts:
                raise RegistryError(
                    f"Event payload {field} {role} origin_path is unsafe"
                )
        seen.add(path)


def _validate_event_payload(event: dict[str, Any]) -> None:
    event_type = str(event.get("type"))
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise RegistryError(f"Payload is not an object for {event_type}")

    if event_type == "REGISTERED":
        expected = f"specs/{event.get('experiment_id')}.json"
        if payload != {"spec": expected}:
            raise RegistryError("REGISTERED payload must point to its immutable spec")
    elif event_type == "STARTED":
        execution_context = payload.get("execution_context")
        if execution_context not in {
            "tester",
            "offline-analysis",
            "static-audit",
        }:
            raise RegistryError("STARTED payload has an invalid execution_context")
        if payload.get("live_trading") is not False:
            raise RegistryError("STARTED payload must set live_trading=false")
        _validate_artifact_list(payload.get("input_artifacts"), "input_artifacts")
        roles = [artifact["role"] for artifact in payload["input_artifacts"]]
        if roles.count("source") != 1 or roles.count("preset") != 1:
            raise RegistryError("STARTED input_artifacts require exactly one source and preset")
        required_roles = {
            "offline-analysis": {"source", "preset", "mt5-report", "symbol-probe"},
            "static-audit": {"source", "preset", "compiled-binary"},
            "tester": {"source", "preset", "compiled-binary", "symbol-probe"},
        }[execution_context]
        missing_roles = required_roles - set(roles)
        if missing_roles:
            raise RegistryError(
                f"STARTED {execution_context} input_artifacts miss roles {sorted(missing_roles)}"
            )
    elif event_type == "COMPLETED":
        verdict = payload.get("verdict")
        if verdict not in VERDICTS:
            raise RegistryError("COMPLETED payload has an invalid verdict")
        technical_valid = payload.get("technical_valid")
        if not isinstance(technical_valid, bool):
            raise RegistryError("COMPLETED payload technical_valid must be boolean")
        if technical_valid is False and verdict != "INVALID_TECHNICAL":
            raise RegistryError(
                "A technically invalid completion must use verdict INVALID_TECHNICAL"
            )
        if technical_valid is True and verdict == "INVALID_TECHNICAL":
            raise RegistryError(
                "A technically valid completion cannot use verdict INVALID_TECHNICAL"
            )
        if payload.get("exit_code") != 0:
            raise RegistryError("COMPLETED payload exit_code must be zero")
        orders_sent = payload.get("orders_sent")
        if not isinstance(orders_sent, int) or isinstance(orders_sent, bool) or orders_sent < 0:
            raise RegistryError("COMPLETED payload orders_sent must be non-negative")
        _validate_artifact_list(payload.get("artifacts"), "artifacts")
        outcome_roles = {
            artifact["role"] for artifact in payload["artifacts"]
        } & {"diagnostic", "audit-result"}
        if not outcome_roles:
            raise RegistryError("COMPLETED artifacts require a diagnostic or audit-result")
    elif event_type == "FAILED":
        _non_empty_string(payload.get("error"), "payload.error")
        exit_code = payload.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
            raise RegistryError("FAILED payload exit_code must be a non-zero integer")
        _validate_artifact_list(payload.get("artifacts", []), "artifacts", allow_empty=True)
    elif event_type == "INVALIDATED":
        _non_empty_string(payload.get("reason"), "payload.reason")
    elif event_type == "REPARSED":
        _non_empty_string(payload.get("reason"), "payload.reason")
        if payload.get("verdict") not in VERDICTS:
            raise RegistryError("REPARSED payload has an invalid verdict")
        _validate_artifact_list(payload.get("artifacts"), "artifacts")
        if "diagnostic" not in {artifact["role"] for artifact in payload["artifacts"]}:
            raise RegistryError("REPARSED artifacts require a diagnostic")
    elif event_type == "DECISION":
        if payload.get("verdict") not in VERDICTS:
            raise RegistryError("DECISION payload has an invalid verdict")
        _non_empty_string(payload.get("rationale"), "payload.rationale")
        _validate_artifact_list(
            payload.get("decision_artifacts"),
            "decision_artifacts",
        )


class ExperimentRegistry:
    """Owns immutable specs and a hash-chained JSONL event stream."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.ledger_path = self.root / "ledger.jsonl"
        self.specs_dir = self.root / "specs"

    def _ensure_layout(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.specs_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked_ledger(self) -> Iterator[Any]:
        self._ensure_layout()
        with self.ledger_path.open("a+", encoding="utf-8", newline="\n") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                stream.seek(0)
                yield stream
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _parse_lines(text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            if not raw_line.strip():
                raise RegistryError(f"Blank ledger line at {line_number}")
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise RegistryError(
                    f"Invalid JSON at ledger line {line_number}: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise RegistryError(f"Ledger line {line_number} is not an object")
            events.append(event)
        return events

    @classmethod
    def verify_events(cls, events: list[dict[str, Any]]) -> None:
        previous_hash = GENESIS_HASH
        for expected_seq, event in enumerate(events, start=1):
            if event.get("schema") != SCHEMA:
                raise RegistryError(f"Invalid schema at sequence {expected_seq}")
            if event.get("seq") != expected_seq:
                raise RegistryError(
                    f"Sequence mismatch: expected {expected_seq}, got {event.get('seq')!r}"
                )
            if event.get("prev_hash") != previous_hash:
                raise RegistryError(f"Broken previous hash at sequence {expected_seq}")
            stored_hash = event.get("event_hash")
            if not isinstance(stored_hash, str) or not HASH_PATTERN.fullmatch(stored_hash):
                raise RegistryError(f"Invalid event hash at sequence {expected_seq}")
            unhashed = dict(event)
            del unhashed["event_hash"]
            calculated_hash = sha256_json(unhashed)
            if stored_hash != calculated_hash:
                raise RegistryError(f"Tampered event at sequence {expected_seq}")
            if event.get("type") not in EVENT_TYPES:
                raise RegistryError(f"Unknown event type at sequence {expected_seq}")
            if not ACTOR_PATTERN.fullmatch(str(event.get("actor", ""))):
                raise RegistryError(f"Invalid actor at sequence {expected_seq}")
            if not HASH_PATTERN.fullmatch(str(event.get("experiment_id", ""))):
                raise RegistryError(f"Invalid experiment ID at sequence {expected_seq}")
            _validate_identifier("run_id", str(event.get("run_id", "")))
            _validate_identifier("event_id", str(event.get("event_id", "")))
            if not isinstance(event.get("payload"), dict):
                raise RegistryError(f"Payload is not an object at sequence {expected_seq}")
            _validate_event_payload(event)
            previous_hash = stored_hash
        cls._verify_transitions(events)

    @staticmethod
    def _verify_transitions(events: list[dict[str, Any]]) -> None:
        states: dict[str, str] = {}
        experiments: dict[str, str] = {}
        execution_contexts: dict[str, str] = {}
        completed_verdicts: dict[str, str] = {}
        for event in events:
            run_id = str(event["run_id"])
            experiment_id = str(event["experiment_id"])
            event_type = str(event["type"])
            previous = states.get(run_id)
            known_experiment = experiments.get(run_id)
            if known_experiment is not None and known_experiment != experiment_id:
                raise RegistryError(f"Run {run_id} changed experiment ID")

            if event_type == "REGISTERED":
                if previous is not None:
                    raise RegistryError(f"Run {run_id} was registered more than once")
                states[run_id] = "REGISTERED"
                experiments[run_id] = experiment_id
            elif event_type == "STARTED":
                if previous != "REGISTERED":
                    raise RegistryError(
                        f"Run {run_id} cannot START from state {previous!r}"
                    )
                states[run_id] = "STARTED"
                execution_contexts[run_id] = str(event["payload"]["execution_context"])
            elif event_type in {"COMPLETED", "FAILED"}:
                if previous != "STARTED":
                    raise RegistryError(
                        f"Run {run_id} cannot {event_type} from state {previous!r}"
                    )
                states[run_id] = event_type
                if event_type == "COMPLETED":
                    context = execution_contexts.get(run_id)
                    if (
                        context in {"offline-analysis", "static-audit"}
                        and event["payload"]["orders_sent"] != 0
                    ):
                        raise RegistryError(
                            f"Run {run_id} sent orders in non-trading context {context}"
                        )
                    output_roles = {
                        artifact["role"] for artifact in event["payload"]["artifacts"]
                    }
                    required_output_roles = {
                        "offline-analysis": {"diagnostic"},
                        "static-audit": {"audit-result"},
                        "tester": {"mt5-report", "audit-result"},
                    }[context]
                    missing_output_roles = required_output_roles - output_roles
                    if missing_output_roles:
                        raise RegistryError(
                            f"Run {run_id} completion misses roles {sorted(missing_output_roles)}"
                        )
                    completed_verdicts[run_id] = str(event["payload"]["verdict"])
            elif event_type == "INVALIDATED":
                if previous not in {"REGISTERED", "STARTED", "COMPLETED", "FAILED"}:
                    raise RegistryError(
                        f"Run {run_id} cannot be INVALIDATED from state {previous!r}"
                    )
                states[run_id] = "INVALIDATED"
            elif event_type in {"REPARSED", "DECISION"}:
                if previous != "COMPLETED":
                    raise RegistryError(
                        f"Run {run_id} cannot emit {event_type} from state {previous!r}"
                    )
                # An annotation does not change the completed run's state.
                if event_type == "DECISION":
                    completed = completed_verdicts[run_id]
                    decision = str(event["payload"]["verdict"])
                    allowed = {
                        "INVALID_TECHNICAL": {"INVALID_TECHNICAL", "GATE_BLOCKED"},
                        "REJECTED": {"REJECTED", "GATE_BLOCKED"},
                        "INCONCLUSIVE": {"INCONCLUSIVE", "REJECTED", "GATE_BLOCKED"},
                        "ELIGIBLE_FOR_NEXT_GATE": VERDICTS,
                        "INFRASTRUCTURE_COMPLETE": {
                            "INFRASTRUCTURE_COMPLETE",
                            "GATE_BLOCKED",
                        },
                        "GATE_BLOCKED": {"GATE_BLOCKED"},
                        "NO_DECISION": VERDICTS,
                    }[completed]
                    if decision not in allowed:
                        raise RegistryError(
                            f"Decision {decision} cannot upgrade completed verdict {completed}"
                        )

    def read_events(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        try:
            text = self.ledger_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RegistryError(f"Cannot read ledger: {exc}") from exc
        events = self._parse_lines(text)
        self.verify_events(events)
        return events

    def verify(self, verify_specs: bool = True) -> list[dict[str, Any]]:
        events = self.read_events()
        if verify_specs:
            for event in events:
                if event["type"] != "REGISTERED":
                    continue
                experiment_id = str(event["experiment_id"])
                spec_path = self.specs_dir / f"{experiment_id}.json"
                if not spec_path.is_file():
                    raise RegistryError(f"Missing immutable spec: {spec_path}")
                spec = _read_json_object(spec_path)
                if sha256_json(spec) != experiment_id:
                    raise RegistryError(f"Spec hash mismatch: {spec_path}")
                validate_spec(spec)
        self._verify_referenced_artifacts(events)
        return events

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _verify_referenced_artifacts(self, events: list[dict[str, Any]]) -> None:
        root = self.root.resolve()
        for event in events:
            payload = event["payload"]
            spec_path = self.specs_dir / f"{event['experiment_id']}.json"
            spec = _read_json_object(spec_path)
            if event["type"] == "STARTED":
                by_role = {
                    artifact["role"]: artifact
                    for artifact in payload["input_artifacts"]
                    if artifact["role"] in {"source", "preset"}
                }
                for role in ("source", "preset"):
                    artifact = by_role[role]
                    if artifact["sha256"] != spec[f"{role}_sha256"]:
                        raise RegistryError(
                            f"STARTED {role} hash does not match immutable spec"
                        )
                    if artifact["origin_path"] != spec[f"{role}_path"]:
                        raise RegistryError(
                            f"STARTED {role} origin does not match immutable spec"
                        )
                declared_inputs = {
                    (item["role"], item["path"]): item
                    for item in spec["input_artifacts"]
                }
                for artifact in payload["input_artifacts"]:
                    if artifact["role"] not in {"mt5-report", "symbol-probe"}:
                        continue
                    key = (artifact["role"], artifact["origin_path"])
                    declared = declared_inputs.get(key)
                    if declared is None:
                        raise RegistryError(
                            f"STARTED {artifact['role']} is absent from immutable spec"
                        )
                    if artifact["sha256"] != declared["sha256"]:
                        raise RegistryError(
                            f"STARTED {artifact['role']} hash does not match immutable spec"
                        )
            for field in ("input_artifacts", "artifacts", "decision_artifacts"):
                for artifact in payload.get(field, []):
                    path = (self.root / artifact["path"]).resolve()
                    try:
                        path.relative_to(root)
                    except ValueError as exc:
                        raise RegistryError(f"Artifact escapes registry root: {path}") from exc
                    if not path.is_file():
                        raise RegistryError(f"Missing registered artifact: {path}")
                    actual = self._sha256_file(path)
                    if actual != artifact["sha256"]:
                        raise RegistryError(f"Registered artifact hash mismatch: {path}")
                    role = artifact["role"]
                    if role == "mt5-report":
                        raw = path.read_bytes()
                        text = (
                            raw.decode("utf-16")
                            if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
                            else raw.decode("utf-8-sig")
                        )
                        if "<html" not in text.lower():
                            raise RegistryError(f"MT5 report artifact is not HTML: {path}")
                    elif role in {"symbol-probe", "diagnostic", "audit-result"}:
                        document = _read_json_object(path)
                        expected_schema = {
                            "symbol-probe": "rsifib-mt5-symbol-probe/v1",
                            "diagnostic": "rsifib-report-diagnostic/v1",
                            "audit-result": "rsifib-audit-result/v1",
                        }[role]
                        if document.get("schema") != expected_schema:
                            raise RegistryError(
                                f"Artifact role {role} has the wrong schema: {path}"
                            )
                        if role == "symbol-probe" and (
                            document.get("tester_only") is not True
                            or document.get("orders_sent") != 0
                        ):
                            raise RegistryError(f"Unsafe symbol probe artifact: {path}")
                        if role in {"diagnostic", "audit-result"} and event["type"] in {
                            "COMPLETED",
                            "REPARSED",
                            "DECISION",
                        }:
                            if document.get("verdict") != payload.get("verdict"):
                                raise RegistryError(
                                    f"Artifact verdict disagrees with {event['type']} payload: {path}"
                                )
                        if role == "diagnostic":
                            provenance = document.get("provenance")
                            policy = document.get("policy")
                            if not isinstance(provenance, dict) or not isinstance(policy, dict):
                                raise RegistryError(
                                    f"Diagnostic lacks provenance or policy: {path}"
                                )
                            data = spec["data"]
                            for key in (
                                "broker",
                                "server",
                                "symbol",
                                "timeframe",
                                "currency",
                                "terminal_build",
                                "deposit",
                                "leverage",
                            ):
                                if provenance.get(key) != data.get(key):
                                    raise RegistryError(
                                        f"Diagnostic {key} disagrees with immutable spec: {path}"
                                    )
                            window = provenance.get("window")
                            authorized_windows = [
                                {"start": item["start"], "end": item["end"]}
                                for item in data["windows"]
                            ]
                            if window not in authorized_windows:
                                raise RegistryError(
                                    f"Diagnostic window is not authorized by immutable spec: {path}"
                                )
                            if policy.get("minimum_trades") != spec["minimum_trades"]:
                                raise RegistryError(
                                    f"Diagnostic minimum_trades disagrees with immutable spec: {path}"
                                )
                            if event["type"] == "COMPLETED":
                                expected_validity = (
                                    "VALID" if payload["technical_valid"] else "INVALID"
                                )
                                if document.get("technical_validity") != expected_validity:
                                    raise RegistryError(
                                        f"Diagnostic technical validity disagrees with payload: {path}"
                                    )

    def _write_spec_once(self, experiment_id: str, spec: dict[str, Any]) -> Path:
        self._ensure_layout()
        path = self.specs_dir / f"{experiment_id}.json"
        content = json.dumps(
            spec, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ) + "\n"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            existing = _read_json_object(path)
            if canonical_json(existing) != canonical_json(spec):
                raise RegistryError(f"Immutable spec collision or corruption: {path}")
            return path
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            # Do not silently continue with a partially written immutable spec.
            raise
        return path

    def register(
        self,
        spec: dict[str, Any],
        actor: str,
        run_id: str | None = None,
    ) -> dict[str, str]:
        validate_spec(spec)
        if not ACTOR_PATTERN.fullmatch(actor):
            raise RegistryError("Actor must contain only letters, digits, dot, dash or underscore")
        experiment_id = sha256_json(spec)
        run_id = run_id if run_id is not None else str(uuid.uuid4())
        _validate_identifier("run_id", run_id)
        self._write_spec_once(experiment_id, spec)
        self.append(
            event_type="REGISTERED",
            actor=actor,
            experiment_id=experiment_id,
            run_id=run_id,
            payload={"spec": f"specs/{experiment_id}.json"},
        )
        return {"experiment_id": experiment_id, "run_id": run_id}

    def append(
        self,
        event_type: str,
        actor: str,
        experiment_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_type = event_type.upper()
        if event_type not in EVENT_TYPES:
            raise RegistryError(f"Unknown event type: {event_type}")
        if not ACTOR_PATTERN.fullmatch(actor):
            raise RegistryError("Invalid actor")
        if not HASH_PATTERN.fullmatch(experiment_id):
            raise RegistryError("experiment_id must be a lowercase SHA-256 hash")
        _validate_identifier("run_id", run_id)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise RegistryError("payload must be an object")

        with self._locked_ledger() as stream:
            events = self._parse_lines(stream.read())
            self.verify_events(events)
            event: dict[str, Any] = {
                "schema": SCHEMA,
                "seq": len(events) + 1,
                "event_id": str(uuid.uuid4()),
                "run_id": run_id,
                "experiment_id": experiment_id,
                "type": event_type,
                "at_utc": utc_now(),
                "actor": actor,
                "payload": payload,
                "prev_hash": events[-1]["event_hash"] if events else GENESIS_HASH,
            }
            event["event_hash"] = sha256_json(event)
            candidate = events + [event]
            self.verify_events(candidate)
            self._verify_referenced_artifacts(candidate)
            stream.seek(0, os.SEEK_END)
            stream.write(canonical_json(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event


def _load_payload(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if value.startswith("@"):
        return _read_json_object(Path(value[1:]))
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Invalid payload JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryError("Payload JSON must be an object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("artifacts/experiments_v3")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    register.add_argument("--spec", type=Path, required=True)
    register.add_argument("--actor", required=True)
    register.add_argument("--run-id")

    append = subparsers.add_parser("append")
    append.add_argument("--type", required=True, choices=sorted(EVENT_TYPES - {"REGISTERED"}))
    append.add_argument("--actor", required=True)
    append.add_argument("--experiment-id", required=True)
    append.add_argument("--run-id", required=True)
    append.add_argument("--payload", help="Inline JSON object or @path/to/object.json")

    subparsers.add_parser("verify")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = ExperimentRegistry(args.root)
    try:
        if args.command == "register":
            result: Any = registry.register(
                _read_json_object(args.spec), args.actor, args.run_id
            )
        elif args.command == "append":
            result = registry.append(
                event_type=args.type,
                actor=args.actor,
                experiment_id=args.experiment_id,
                run_id=args.run_id,
                payload=_load_payload(args.payload),
            )
        else:
            events = registry.verify()
            result = {
                "valid": True,
                "events": len(events),
                "last_hash": events[-1]["event_hash"] if events else GENESIS_HASH,
            }
    except RegistryError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
