"""Offline package-validation tests, including malformed and hostile fixtures."""
from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validate_skill as validator


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "defensive-design"
        self.root.mkdir()
        self.write("SKILL.md", '''---
name: defensive-design
description: A minimal validation fixture.
metadata:
  version: "1.2.0"
---
# Core
[Guide](references/guide.md)
''')
        self.write("references/guide.md", "# Guide\n\nA fixture.\n")
        self.write("agents/openai.yaml", '''interface:
  display_name: Defensive Design
  short_description: Fixture description
  default_prompt: Use $defensive-design to review.
''')
        self.write("evals/defensive-design.prompts.csv", '''id,should_trigger,prompt
test-01,true,"Review this boundary."
test-02,false,"Fix spelling."
''')
        self.write("evals/behavior-rubric.md", '''# Rubric
| ID | Expected behavior |
|---|---|
| test-01 | Reviews the boundary. |
| test-02 | Fixes spelling only. |
''')

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def change(self, path, old, new):
        target = self.root / path
        target.write_text(target.read_text().replace(old, new))

    def errors(self):
        return "\n".join(validator.validate(self.root))

    def test_valid_package(self):
        self.assertEqual(validator.validate(self.root), [])

    def test_missing_frontmatter(self):
        self.write("SKILL.md", "# No frontmatter\n")
        self.assertIn("frontmatter", self.errors())

    def test_duplicate_yaml_keys(self):
        self.change("SKILL.md", "description:", "name: overwritten\ndescription:")
        self.assertIn("duplicate YAML key", self.errors())

    def test_unsafe_yaml_tag_is_rejected(self):
        self.change("SKILL.md", "A minimal validation fixture.", "!!python/object/apply:os.system ['false']")
        self.assertIn("invalid YAML", self.errors())

    def test_deep_yaml_is_reported_without_a_traceback(self):
        issues = []
        validator.mapping("nested: " + "[" * 1500 + "0" + "]" * 1500, "fixture", issues)
        self.assertTrue(issues)
        self.assertIn("invalid YAML", issues[0])

    def test_invalid_name(self):
        self.change("SKILL.md", "name: defensive-design", "name: Defensive--Design")
        self.assertIn("invalid name", self.errors())

    def test_directory_name_mismatch(self):
        self.change("SKILL.md", "name: defensive-design", "name: other-skill")
        self.assertIn("match package directory", self.errors())

    def test_description_length(self):
        self.change("SKILL.md", "A minimal validation fixture.", "x" * 1025)
        self.assertIn("description", self.errors())

    def test_metadata_must_be_strings(self):
        self.change("SKILL.md", 'version: "1.2.0"', 'version: 12')
        self.assertIn("string-valued metadata", self.errors())

    def test_unknown_metadata_field(self):
        self.change("SKILL.md", "description:", "unexpected: true\ndescription:")
        self.assertIn("unknown frontmatter field", self.errors())

    def test_missing_link(self):
        self.change("SKILL.md", "references/guide.md", "references/missing.md")
        self.assertIn("missing local link target", self.errors())

    def test_missing_anchor(self):
        self.change("SKILL.md", "references/guide.md", "references/guide.md#absent")
        self.assertIn("missing local heading anchor", self.errors())

    def test_valid_anchor(self):
        self.change("SKILL.md", "references/guide.md", "references/guide.md#guide")
        self.assertEqual(validator.validate(self.root), [])

    def test_encoded_traversal(self):
        self.change("SKILL.md", "references/guide.md", "%2e%2e/private.md")
        self.assertIn("escapes package root", self.errors())

    def test_symlink_escape(self):
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("# Outside\n")
        link = self.root / "references/guide.md"
        link.unlink()
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        self.assertIn("escapes package root", self.errors())

    def test_absolute_and_backslash_paths(self):
        for path in ("/tmp/test.md", "..%5cprivate.md", "file:///tmp/test.md"):
            with self.subTest(path=path):
                errors = []
                validator.check_links(self.root / "SKILL.md", f"[X]({path})", self.root, errors)
                self.assertTrue(errors)

    def test_fenced_examples_are_not_links(self):
        with (self.root / "references/guide.md").open("a") as stream:
            stream.write("\n```text\n[Not a link](missing.md)\n```\n")
        self.assertEqual(validator.validate(self.root), [])

    def test_unreferenced_resource(self):
        self.write("references/unreachable.md", "# Unreachable\n")
        self.assertIn("missing direct link", self.errors())

    def test_host_prompt_must_invoke_skill(self):
        self.change("agents/openai.yaml", "$defensive-design", "$another-skill")
        self.assertIn("must invoke the skill", self.errors())

    def test_duplicate_eval_id(self):
        self.change("evals/defensive-design.prompts.csv", "test-02", "test-01")
        self.assertIn("duplicate case ID", self.errors())

    def test_invalid_eval_boolean(self):
        self.change("evals/defensive-design.prompts.csv", "test-01,true", "test-01,yes")
        self.assertIn("invalid id or boolean", self.errors())

    def test_missing_rubric_case(self):
        self.change("evals/behavior-rubric.md", "test-02", "test-03")
        self.assertIn("exactly match", self.errors())

    def test_duplicate_rubric_case(self):
        with (self.root / "evals/behavior-rubric.md").open("a") as stream:
            stream.write("| test-01 | Duplicate row. |\n")
        self.assertIn("duplicate case ID", self.errors())

    def test_requires_negative_coverage(self):
        self.change("evals/defensive-design.prompts.csv", "test-02,false", "test-02,true")
        self.assertIn("positive and negative coverage", self.errors())

    def test_multiline_csv_is_supported(self):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["id", "should_trigger", "prompt"])
        writer.writerow(["test-01", "true", "Review:\ncode, more code\nline 2"])
        writer.writerow(["test-02", "false", "Fix spelling"])
        self.write("evals/defensive-design.prompts.csv", stream.getvalue())
        self.assertEqual(validator.validate(self.root), [])

    def test_missing_dependency_is_actionable(self):
        with patch.object(validator, "yaml", None):
            self.assertIn("PyYAML is required", self.errors())

    def test_core_budget(self):
        with (self.root / "SKILL.md").open("a") as stream:
            stream.write("x" * validator.MAX_CORE_BYTES)
        self.assertIn("core size budget", self.errors())

    def test_invalid_utf8(self):
        (self.root / "references/guide.md").write_bytes(b"\xff")
        self.assertIn("utf-8", self.errors())

    def test_oversized_file(self):
        (self.root / "references/guide.md").write_bytes(b"x" * (validator.MAX_FILE_BYTES + 1))
        self.assertIn("size budget", self.errors())

    def test_actual_repository(self):
        self.assertEqual(validator.validate(Path(__file__).resolve().parents[1]), [])


if __name__ == "__main__":
    unittest.main()
