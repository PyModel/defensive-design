"""Evidence aggregation is fail-closed; these tests do not evaluate a model."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import evaluate_skill as evaluator


class EvaluationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.skill = self.repo / "skills" / "defensive-design"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("# Small skill\nRead only applicable guidance.\n", encoding="utf-8")
        (self.repo / "evals").mkdir()
        (self.repo / "evals" / "defensive-design.prompts.csv").write_text(
            'id,should_trigger,prompt\ntest-01,true,"Review this boundary."\n'
            'test-02,false,"Fix the spelling."\n', encoding="utf-8")
        (self.repo / "evals" / "behavior-rubric.md").write_text("Private expected outcomes.\n", encoding="utf-8")
        self.context_path = self.root / "context.json"
        self.context_path.write_text(json.dumps({
            "host": "test host", "model": "test model", "system_instructions": "recorded instructions",
            "tools": [], "permissions": "offline disposable workspace", "date": "2026-11-18",
            "fixture_revision": "synthetic", "notes": "unit-test data, not a model evaluation",
        }), encoding="utf-8")
        self.run_dir = self.root / "run"
        evaluator.prepare(self.repo, self.run_dir, self.context_path)
        self.responses = self.root / "responses.jsonl"
        self.triggers = self.root / "triggers.jsonl"
        self.grades = self.root / "grades.jsonl"
        self.response_rows: list[dict[str, Any]] = [{"id": identifier, "arm": arm, "answer": "Observed output for " + identifier}
                              for identifier in ("test-01", "test-02") for arm in ("skill", "baseline")]
        self.grade_rows = [{"id": row["id"], "arm": row["arm"], "verdict": "pass",
                            "evidence": ["Observed output"], "reason": "synthetic grader assertion", "critical": False}
                           for row in self.response_rows]
        self.trigger_rows = [{"id": "test-01", "selected": True}, {"id": "test-02", "selected": False}]
        self.write_evidence()

    def write_rows(self, path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def write_evidence(self) -> None:
        self.write_rows(self.responses, self.response_rows)
        self.write_rows(self.grades, self.grade_rows)
        self.write_rows(self.triggers, self.trigger_rows)

    def report(self) -> dict:
        return evaluator.report(self.run_dir, self.responses, self.triggers, self.grades)

    def test_prepare_does_not_leak_labels_or_rubric_to_executor_inputs(self) -> None:
        rows = evaluator.json_lines(self.run_dir / "inputs.jsonl")
        self.assertEqual([set(row) for row in rows], [{"id", "prompt"}] * 2)
        self.assertEqual(sorted(path.name for path in (self.run_dir / "skill").iterdir()), ["SKILL.md"])
        self.assertEqual((self.run_dir / "skill" / "SKILL.md").read_bytes(), (self.skill / "SKILL.md").read_bytes())

    def test_prepare_never_overwrites_an_existing_run(self) -> None:
        marker = self.run_dir / "keep"
        marker.write_text("preserve me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            evaluator.prepare(self.repo, self.run_dir, self.context_path)
        self.assertEqual(marker.read_text(), "preserve me")

    def test_prepare_cleanup_failure_preserves_primary_and_secondary_errors(self) -> None:
        primary = OSError("snapshot write failed")
        cleanup = PermissionError("cleanup failed")
        with (
            patch.object(evaluator, "write_json", side_effect=primary),
            patch.object(evaluator.shutil, "rmtree", side_effect=cleanup),
            self.assertRaises(OSError) as caught,
        ):
            evaluator.prepare(self.repo, self.root / "partial", self.context_path)
        self.assertIs(caught.exception, primary)
        self.assertTrue(caught.exception.__cause__ is cleanup or getattr(caught.exception, "__notes__", None))

    def test_complete_evidence_has_exact_denominators_and_hashes(self) -> None:
        result = self.report()
        self.assertEqual(result["trigger"]["total"], 2)
        self.assertEqual(result["trigger"]["true_positive"], 1)
        self.assertEqual(result["trigger"]["true_negative"], 1)
        self.assertEqual(result["paired"]["both_pass"], 2)
        self.assertEqual(result["behavior"]["skill"]["pass_rate"], 1)
        self.assertEqual(set(result["evidence_sha256"]), {"responses", "triggers", "grades"})
        self.assertIsNone(result["core"]["token_count"])

    def test_blocked_results_remain_in_denominator_and_pairing(self) -> None:
        self.grade_rows[0].update(verdict="blocked", evidence=[], reason="Tool access unavailable")
        self.grade_rows[1].update(verdict="fail", critical=True)
        self.write_evidence()
        result = self.report()
        self.assertEqual(result["behavior"]["skill"],
                         {"total": 2, "pass": 1, "fail": 0, "blocked": 1,
                          "pass_rate": 0.5, "critical_failures": 0})
        self.assertEqual(result["behavior"]["baseline"]["critical_failures"], 1)
        self.assertEqual(result["paired"]["neither_pass"], 1)

    def test_trigger_false_positives_and_negatives_are_not_swapped(self) -> None:
        self.trigger_rows = [{"id": "test-01", "selected": False}, {"id": "test-02", "selected": True}]
        self.write_evidence()
        result = self.report()["trigger"]
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["false_negative"], 1)
        self.assertEqual(result["recall"], 0)

    def test_no_positive_predictions_has_undefined_precision(self) -> None:
        for row in self.trigger_rows:
            row["selected"] = False
        self.write_evidence()
        self.assertIsNone(self.report()["trigger"]["precision"])

    def test_missing_responses_and_grades_are_rejected(self) -> None:
        for path, rows in ((self.responses, self.response_rows), (self.grades, self.grade_rows)):
            with self.subTest(path=path.name):
                self.write_evidence()
                self.write_rows(path, rows[:-1])
                with self.assertRaisesRegex(evaluator.EvidenceError, "Incomplete"):
                    self.report()

    def test_duplicate_responses_and_grades_are_rejected(self) -> None:
        for path, rows in ((self.responses, self.response_rows), (self.grades, self.grade_rows)):
            with self.subTest(path=path.name):
                self.write_evidence()
                self.write_rows(path, [*rows, rows[0]])
                with self.assertRaisesRegex(evaluator.EvidenceError, "Duplicate"):
                    self.report()

    def test_unknown_ids_arms_and_extra_fields_are_rejected(self) -> None:
        changes: list[dict[str, Any]] = [{"id": "test-99"}, {"arm": "unknown"}, {"arm": []}, {"unexpected": True}]
        for change in changes:
            with self.subTest(change=change):
                rows = [dict(row) for row in self.response_rows]
                rows[0].update(change)
                self.write_rows(self.responses, rows)
                with self.assertRaises(evaluator.EvidenceError):
                    self.report()

    def test_grade_cannot_claim_unobserved_evidence(self) -> None:
        self.grade_rows[0]["evidence"] = ["A claim the answer never made"]
        self.write_evidence()
        with self.assertRaisesRegex(evaluator.EvidenceError, "absent"):
            self.report()

    def test_critical_failure_cannot_pass(self) -> None:
        self.grade_rows[0]["critical"] = True
        self.write_evidence()
        with self.assertRaisesRegex(evaluator.EvidenceError, "Critical"):
            self.report()

    def test_nonblocked_grade_requires_evidence(self) -> None:
        for verdict in ("pass", "fail"):
            self.grade_rows[0].update(verdict=verdict, evidence=[])
            self.write_evidence()
            with self.assertRaisesRegex(evaluator.EvidenceError, "observable evidence"):
                self.report()

    def test_trigger_incompleteness_duplicates_and_truthy_integers_are_rejected(self) -> None:
        for rows in ([self.trigger_rows[0]], [*self.trigger_rows, self.trigger_rows[0]],
                     [{"id": "test-01", "selected": 1}, self.trigger_rows[1]]):
            self.write_rows(self.triggers, rows)
            with self.assertRaises(evaluator.EvidenceError):
                self.report()

    def test_modified_skill_inputs_rubric_and_corpus_are_rejected(self) -> None:
        for path in (self.run_dir / "skill" / "SKILL.md", self.run_dir / "inputs.jsonl",
                     self.run_dir / "rubric.md", self.run_dir / "corpus.csv"):
            with self.subTest(path=path.name):
                old = path.read_bytes()
                try:
                    path.write_bytes(old + b"altered\n")
                    with self.assertRaises(evaluator.EvidenceError):
                        self.report()
                finally:
                    path.write_bytes(old)

    def test_snapshot_cannot_silently_add_a_file(self) -> None:
        (self.run_dir / "skill" / "extra.md").write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(evaluator.EvidenceError, "differs"):
            self.report()

    def test_archived_package_preserves_evidence_without_a_second_skill_directory(self) -> None:
        before = self.report()
        core = (self.run_dir / "skill" / "SKILL.md").read_bytes()
        archive: dict[str, Any] = {"format": "defensive-design-package-v1",
                   "files": {"SKILL.md": base64.b64encode(core).decode("ascii")}}
        (self.run_dir / "package.json").write_text(json.dumps(archive), encoding="utf-8")
        shutil.rmtree(self.run_dir / "skill")
        self.assertEqual(self.report(), before)
        for change in ({"SKILL.md": "invalid*base64"}, {"../SKILL.md": archive["files"]["SKILL.md"]},
                       {"SKILL.md": base64.b64encode(b"altered").decode("ascii")}):
            (self.run_dir / "package.json").write_text(json.dumps({**archive, "files": change}), encoding="utf-8")
            with self.assertRaises(evaluator.EvidenceError):
                self.report()

    def test_symlink_in_source_is_rejected(self) -> None:
        (self.skill / "outside.md").symlink_to(self.context_path)
        with self.assertRaisesRegex(evaluator.EvidenceError, "symlink"):
            evaluator.prepare(self.repo, self.root / "unsafe", self.context_path)
        self.assertFalse((self.root / "unsafe").exists())

    def test_run_cannot_be_nested_in_installable_package(self) -> None:
        with self.assertRaisesRegex(evaluator.EvidenceError, "installable"):
            evaluator.prepare(self.repo, self.skill / "unsafe", self.context_path)

    def test_json_duplicate_keys_nonfinite_values_and_blank_records_are_rejected(self) -> None:
        for raw in ('{"id":"test-01","id":"test-02"}\n', '{"x":NaN}\n',
                    '{"x":Infinity}\n', '{}\n\n', '[1,2]\n'):
            with self.subTest(raw=raw):
                self.triggers.write_text(raw, encoding="utf-8")
                with self.assertRaises(evaluator.EvidenceError):
                    self.report()

    def test_invalid_unicode_is_rejected_cleanly_by_library_and_cli(self) -> None:
        self.response_rows[0]["answer"] = "\ud800"
        self.write_evidence()
        with self.assertRaisesRegex(evaluator.EvidenceError, "Unicode surrogate"):
            self.report()
        result = subprocess.run(
            [sys.executable, str(Path(evaluator.__file__).resolve()), "report", "--run", str(self.run_dir),
             "--responses", str(self.responses), "--triggers", str(self.triggers),
             "--grades", str(self.grades), "--out", str(self.root / "invalid.json")],
            cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "invalid.json").exists())

    def test_oversized_input_is_rejected_before_parsing(self) -> None:
        path = self.root / "large"
        path.write_bytes(b"12345")
        with self.assertRaisesRegex(evaluator.EvidenceError, "exceeds"):
            evaluator.read_bytes(path, limit=4)

    def test_bad_context_does_not_create_a_run(self) -> None:
        context = json.loads(self.context_path.read_text())
        context["date"] = "sometime"
        self.context_path.write_text(json.dumps(context), encoding="utf-8")
        with self.assertRaises(evaluator.EvidenceError):
            evaluator.prepare(self.repo, self.root / "bad", self.context_path)
        self.assertFalse((self.root / "bad").exists())

    def test_cli_works_from_unrelated_working_directory_and_wont_overwrite(self) -> None:
        script = Path(evaluator.__file__).resolve()
        output = self.root / "summary.json"
        command = [sys.executable, str(script), "report", "--run", str(self.run_dir),
                   "--responses", str(self.responses), "--triggers", str(self.triggers),
                   "--grades", str(self.grades), "--out", str(output)]
        first = subprocess.run(command, cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = output.read_bytes()
        second = subprocess.run(command, cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
