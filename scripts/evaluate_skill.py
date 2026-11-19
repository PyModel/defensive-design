#!/usr/bin/env python3
"""Prepare uncontaminated eval inputs and verify externally produced evidence.

This program does not invoke a model or infer quality from keywords. Its report is
an auditable aggregation of supplied trigger decisions and attributed judgments.
Run with --help from any working directory; no optional dependency is required.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import io
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 2000
MAX_TEXT = 128 * 1024
MAX_PACKAGE_FILES = 128
MAX_PACKAGE_BYTES = 4 * 1024 * 1024
CASE_ID = re.compile(r"test-\d{2,}")
ARMS = {"skill", "baseline"}
CONTEXT_FIELDS = {
    "host", "model", "system_instructions", "tools", "permissions", "date",
    "fixture_revision", "notes",
}


class EvidenceError(ValueError):
    """Invalid or incomplete evaluation evidence; never silently graded as a pass."""


def fail(message: str) -> NoReturn:
    raise EvidenceError(message)


def read_bytes(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        fail(f"Not a regular, non-symlink input file: {path}")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        fail(f"Input exceeds {limit} bytes: {path}")
    return data


def read_text(path: Path, limit: int = MAX_FILE_BYTES) -> str:
    try:
        return read_bytes(path, limit).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"Input is not UTF-8: {path}") from exc


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value: str) -> None:
    fail(f"Non-finite JSON number is not permitted: {value}")


def decode_json(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise EvidenceError(f"Invalid JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        fail(f"Expected a JSON object in {label}")
    return value


def json_file(path: Path) -> dict[str, Any]:
    return decode_json(read_text(path), str(path))


def json_lines(path: Path) -> list[dict[str, Any]]:
    raw = read_text(path)
    lines = raw.splitlines()
    if not lines or len(lines) > MAX_RECORDS:
        fail(f"Expected 1..{MAX_RECORDS} JSONL records: {path}")
    records = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            fail(f"Blank JSONL record at {path}:{number}")
        records.append(decode_json(line, f"{path}:{number}"))
    return records


def exact_fields(row: dict[str, Any], fields: set[str], label: str) -> None:
    if set(row) != fields:
        fail(f"{label}: expected fields {sorted(fields)}, found {sorted(row)}")


def nonempty(value: Any, label: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: expected nonempty text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise EvidenceError(f"{label}: text contains an invalid Unicode surrogate") from exc
    if size > limit:
        fail(f"{label}: text exceeds {limit} UTF-8 bytes")
    return value


def case_id(value: Any) -> str:
    identifier = nonempty(value, "id", 64)
    if not CASE_ID.fullmatch(identifier):
        fail(f"Invalid case id: {identifier}")
    return identifier


def read_corpus(path: Path) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(read_text(path)), strict=True)
    if reader.fieldnames != ["id", "should_trigger", "prompt"]:
        fail("Corpus must have exactly id,should_trigger,prompt columns")
    result = []
    seen: set[str] = set()
    for row in reader:
        if set(row) != {"id", "should_trigger", "prompt"} or any(v is None for v in row.values()):
            fail("Malformed corpus row")
        identifier = case_id(row["id"])
        if identifier in seen:
            fail(f"Duplicate corpus id: {identifier}")
        seen.add(identifier)
        if row["should_trigger"] not in {"true", "false"}:
            fail(f"Invalid should_trigger for {identifier}")
        result.append({"id": identifier, "should_trigger": row["should_trigger"] == "true",
                       "prompt": nonempty(row["prompt"], identifier)})
    if not result or len(result) > MAX_RECORDS // 2:
        fail(f"Corpus must contain 1..{MAX_RECORDS // 2} cases")
    return result


def package_files(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        fail(f"Package is not a regular directory: {root}")
    files: dict[str, bytes] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            fail(f"Package symlink is not permitted: {relative}")
        if path.is_dir():
            continue
        data = read_bytes(path, MAX_PACKAGE_BYTES)
        total += len(data)
        files[relative.as_posix()] = data
        if len(files) > MAX_PACKAGE_FILES or total > MAX_PACKAGE_BYTES:
            fail("Package exceeds file-count or byte budget")
    if "SKILL.md" not in files:
        fail("Package has no SKILL.md")
    return files


def package_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, data in sorted(files.items()):
        digest.update(relative.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()


def snapshot_files(run: Path) -> dict[str, bytes]:
    """Read a live executor copy or an archive without extra discoverable SKILL.md files."""
    if (run / "skill").exists() or (run / "skill").is_symlink():
        return package_files(run / "skill")
    archive = json_file(run / "package.json")
    exact_fields(archive, {"format", "files"}, "package archive")
    if archive["format"] != "defensive-design-package-v1" or not isinstance(archive["files"], dict):
        fail("Invalid package archive format")
    if not 0 < len(archive["files"]) <= MAX_PACKAGE_FILES:
        fail("Invalid package archive file count")
    files: dict[str, bytes] = {}
    total = 0
    for name, encoded in archive["files"].items():
        if (not isinstance(name, str) or not name or "\\" in name or "\0" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            fail("Package archive paths must be normalized relative paths")
        if not isinstance(encoded, str) or len(encoded) > (MAX_PACKAGE_BYTES * 4 // 3 + 4):
            fail("Invalid or oversized base64 package content")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise EvidenceError("Invalid base64 package content") from exc
        total += len(data)
        if total > MAX_PACKAGE_BYTES:
            fail("Package archive exceeds byte budget")
        files[name] = data
    if "SKILL.md" not in files:
        fail("Package archive has no SKILL.md")
    return files


def validate_context(context: dict[str, Any]) -> None:
    exact_fields(context, CONTEXT_FIELDS, "context")
    for field in CONTEXT_FIELDS - {"tools"}:
        nonempty(context[field], f"context.{field}")
    if not isinstance(context["tools"], list) or not all(isinstance(x, str) and x.strip()
                                                       for x in context["tools"]):
        fail("context.tools must be a list of nonempty strings")
    for tool in context["tools"]:
        nonempty(tool, "context.tools item")
    try:
        datetime.fromisoformat(context["date"])
    except ValueError as exc:
        raise EvidenceError("context.date must be an ISO 8601 date or timestamp") from exc


def write_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    stream = path.open("xb")
    try:
        with stream:
            stream.write(data)
    except BaseException as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            exc.add_note("Failed to remove incomplete output; inspect the output path before retrying.")
        raise


def prepare(repo: Path, out: Path, context_path: Path) -> dict[str, Any]:
    """Create a new run directory; never replace an existing run or source tree."""
    repo = repo.resolve()
    out = out.absolute()
    if out.resolve().is_relative_to(repo / "skills"):
        fail("A run directory must not be created inside the installable skills tree")
    context = json_file(context_path)
    validate_context(context)
    corpus_path = repo / "evals" / "defensive-design.prompts.csv"
    cases = read_corpus(corpus_path)
    files = package_files(repo / "skills" / "defensive-design")
    rubric = read_bytes(repo / "evals" / "behavior-rubric.md")
    inputs = "".join(json.dumps({"id": row["id"], "prompt": row["prompt"]}, ensure_ascii=False)
                     + "\n" for row in cases)
    manifest = {
        "schema_version": 1, "context": context, "cases": cases,
        "corpus_sha256": hashlib.sha256(read_bytes(corpus_path)).hexdigest(),
        "rubric_sha256": hashlib.sha256(rubric).hexdigest(),
        "inputs_sha256": hashlib.sha256(inputs.encode("utf-8")).hexdigest(),
        "package_sha256": package_digest(files),
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    # mkdir is exclusive. Only a directory created by this invocation is cleaned up.
    out.mkdir()
    try:
        for name, data in files.items():
            target = out / "skill" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (out / "inputs.jsonl").write_text(inputs, encoding="utf-8", newline="\n")
        # Private judging material lives separately from the executor skill/input set.
        (out / "rubric.md").write_bytes(rubric)
        (out / "corpus.csv").write_bytes(read_bytes(corpus_path))
        write_json(out / "manifest.json", manifest)
    except BaseException as exc:
        try:
            shutil.rmtree(out)
        except OSError:
            exc.add_note("Failed to remove incomplete run; inspect the run directory before retrying.")
        raise
    return manifest


def validate_manifest(run: Path) -> tuple[dict[str, Any], dict[str, bool]]:
    manifest = json_file(run / "manifest.json")
    exact_fields(manifest, {"schema_version", "context", "cases", "corpus_sha256", "rubric_sha256",
                            "inputs_sha256", "package_sha256", "files"}, "manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        fail("Unsupported manifest schema")
    if not isinstance(manifest["context"], dict):
        fail("Invalid context in manifest")
    validate_context(manifest["context"])
    if not isinstance(manifest["cases"], list) or not 0 < len(manifest["cases"]) <= MAX_RECORDS // 2:
        fail("Invalid manifest cases")
    expected: dict[str, bool] = {}
    inputs = []
    for row in manifest["cases"]:
        if not isinstance(row, dict):
            fail("Invalid manifest case")
        exact_fields(row, {"id", "prompt", "should_trigger"}, "manifest case")
        identifier = case_id(row["id"])
        if identifier in expected or type(row["should_trigger"]) is not bool:
            fail("Duplicate id or non-boolean should_trigger in manifest")
        expected[identifier] = row["should_trigger"]
        inputs.append({"id": identifier, "prompt": nonempty(row["prompt"], identifier)})
    actual_inputs = json_lines(run / "inputs.jsonl")
    if actual_inputs != inputs:
        fail("Executor inputs differ from manifest cases")
    if read_corpus(run / "corpus.csv") != manifest["cases"]:
        fail("Source corpus differs from manifest cases")
    for path, field in ((run / "inputs.jsonl", "inputs_sha256"), (run / "rubric.md", "rubric_sha256"),
                        (run / "corpus.csv", "corpus_sha256")):
        if hashlib.sha256(read_bytes(path)).hexdigest() != manifest[field]:
            fail(f"Snapshot digest mismatch: {path.name}")
    files = snapshot_files(run)
    if ({name: hashlib.sha256(data).hexdigest() for name, data in files.items()} != manifest["files"]
            or package_digest(files) != manifest["package_sha256"]):
        fail("Skill snapshot differs from manifest")
    return manifest, expected


def keyed_rows(path: Path, expected: set[str], kind: str) -> dict[tuple[str, str], dict[str, Any]]:
    fields = {"id", "arm", "answer"} if kind == "responses" else {
        "id", "arm", "verdict", "evidence", "reason", "critical"}
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in json_lines(path):
        exact_fields(row, fields, kind)
        identifier = case_id(row["id"])
        if identifier not in expected or not isinstance(row["arm"], str) or row["arm"] not in ARMS:
            fail(f"Unknown case or arm in {kind}")
        key = (identifier, row["arm"])
        if key in result:
            fail(f"Duplicate {kind} result: {key}")
        result[key] = row
    wanted = {(identifier, arm) for identifier in expected for arm in ARMS}
    if set(result) != wanted:
        fail(f"Incomplete {kind}: missing {sorted(wanted - set(result))}")
    return result


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def report(run: Path, responses_path: Path, triggers_path: Path, grades_path: Path) -> dict[str, Any]:
    manifest, truth = validate_manifest(run)
    identifiers = set(truth)
    responses = keyed_rows(responses_path, identifiers, "responses")
    grades = keyed_rows(grades_path, identifiers, "grades")
    for key, row in responses.items():
        nonempty(row["answer"], f"answer {key}")
    for key, row in grades.items():
        if (not isinstance(row["verdict"], str) or row["verdict"] not in {"pass", "fail", "blocked"}
                or type(row["critical"]) is not bool):
            fail(f"Invalid grade verdict or critical flag: {key}")
        nonempty(row["reason"], f"reason {key}")
        evidence = row["evidence"]
        if not isinstance(evidence, list) or len(evidence) > 32:
            fail(f"Evidence must be a list of at most 32 quotes: {key}")
        if row["verdict"] != "blocked" and not evidence:
            fail(f"A pass/fail judgment needs observable evidence: {key}")
        if row["critical"] and row["verdict"] == "pass":
            fail(f"Critical failure cannot be a pass: {key}")
        for quote in evidence:
            nonempty(quote, f"evidence {key}")
            if quote not in responses[key]["answer"]:
                fail(f"Evidence quote is absent from the answer: {key}")
    selected: dict[str, bool] = {}
    for row in json_lines(triggers_path):
        exact_fields(row, {"id", "selected"}, "trigger")
        identifier = case_id(row["id"])
        if identifier not in truth or identifier in selected or type(row["selected"]) is not bool:
            fail("Unknown/duplicate trigger id or non-boolean decision")
        selected[identifier] = row["selected"]
    if set(selected) != identifiers:
        fail(f"Incomplete trigger results: missing {sorted(identifiers - set(selected))}")
    matrix = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    for identifier, expected in truth.items():
        actual = selected[identifier]
        category = ("true_" if actual == expected else "false_") + ("positive" if actual else "negative")
        matrix[category] += 1
    behavior = {}
    for arm in sorted(ARMS):
        arm_grades = [row for key, row in grades.items() if key[1] == arm]
        counts = Counter(row["verdict"] for row in arm_grades)
        behavior[arm] = {"total": len(arm_grades), **{v: counts[v] for v in ("pass", "fail", "blocked")},
                         "pass_rate": rate(counts["pass"], len(arm_grades)),
                         "critical_failures": sum(row["critical"] for row in arm_grades)}
    paired = {"both_pass": 0, "skill_only_pass": 0, "baseline_only_pass": 0, "neither_pass": 0}
    for identifier in truth:
        skill_pass = grades[(identifier, "skill")]["verdict"] == "pass"
        baseline_pass = grades[(identifier, "baseline")]["verdict"] == "pass"
        outcome = ("both_pass" if skill_pass and baseline_pass else "skill_only_pass" if skill_pass
                   else "baseline_only_pass" if baseline_pass else "neither_pass")
        paired[outcome] += 1
    core = snapshot_files(run)["SKILL.md"]
    return {
        "schema_version": 1, "context": manifest["context"],
        "package_sha256": manifest["package_sha256"], "corpus_sha256": manifest["corpus_sha256"],
        "rubric_sha256": manifest["rubric_sha256"],
        "evidence_sha256": {name: hashlib.sha256(read_bytes(path)).hexdigest() for name, path in (
            ("responses", responses_path), ("triggers", triggers_path), ("grades", grades_path))},
        "trigger": {"total": len(truth), **matrix,
                    "precision": rate(matrix["true_positive"], matrix["true_positive"] + matrix["false_positive"]),
                    "recall": rate(matrix["true_positive"], matrix["true_positive"] + matrix["false_negative"])},
        "behavior": behavior, "paired": paired,
        "core": {"bytes": len(core), "words": len(core.decode("utf-8").split()),
                 "token_count": None, "token_note": "Byte and whitespace-word counts are not model token counts."},
        "interpretation": "Counts aggregate supplied judgments, not an automated proof of answer quality. "
                          "Blocked cases remain in the denominator. Exact quotes establish traceability, "
                          "not correctness or grader independence. Context records host and isolation limitations.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("prepare", help="Freeze the skill and produce executor inputs without labels")
    setup.add_argument("--repo", type=Path, required=True)
    setup.add_argument("--out", type=Path, required=True)
    setup.add_argument("--context", type=Path, required=True)
    check = commands.add_parser("report", help="Validate complete evidence and aggregate declared judgments")
    check.add_argument("--run", type=Path, required=True)
    check.add_argument("--responses", type=Path, required=True)
    check.add_argument("--triggers", type=Path, required=True)
    check.add_argument("--grades", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            manifest = prepare(args.repo, args.out, args.context)
            print(f"Prepared {len(manifest['cases'])} cases; skill SHA-256 {manifest['package_sha256']}")
        else:
            result = report(args.run, args.responses, args.triggers, args.grades)
            write_json(args.out, result)
            print(json.dumps({"trigger": result["trigger"], "behavior": result["behavior"],
                              "paired": result["paired"]}, sort_keys=True))
    except (EvidenceError, OSError, csv.Error, UnicodeError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
