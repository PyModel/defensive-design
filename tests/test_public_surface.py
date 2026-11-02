"""Pin the documented compatibility surface (see AGENTS.md and CHANGELOG 1.3.0).

Removing or renaming anything here breaks installed copies or callers of the
example. Do that only with a documented migration, then update this list.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import verify_reference as harness

PACKAGE = Path(__file__).resolve().parents[1] / "skills" / "defensive-design"
PUBLIC_PATHS = {
    "SKILL.md",
    "LICENSE",
    "agents/openai.yaml",
    "assets/assessment-template.md",
    "references/architecture-adaptation.md",
    "references/code-level-design.md",
    "references/defensive-checklists.md",
    "references/failure-taxonomy.md",
    "references/resilient_http_example.py",
    "references/secure-coding-overlay.md",
    "references/sources.md",
    "references/verification-and-chaos.md",
}
FETCH_STATUS = {
    "SUCCESS": "success",
    "NOT_FOUND": "not_found",
    "INVALID_REQUEST": "invalid_request",
    "UNAUTHENTICATED": "unauthenticated",
    "FORBIDDEN": "forbidden",
    "RATE_LIMITED": "rate_limited",
    "INVALID_PAYLOAD": "invalid_payload",
    "UNEXPECTED_RESPONSE": "unexpected_response",
    "TEMPORARILY_UNAVAILABLE": "temporarily_unavailable",
    "OVERLOADED": "overloaded",
    "CANCELLED": "cancelled",
    "INTERNAL_ERROR": "internal_error",
}


class PublicSurfaceTests(unittest.TestCase):
    def test_package_paths_are_preserved(self) -> None:
        missing = sorted(path for path in PUBLIC_PATHS if not (PACKAGE / path).is_file())
        self.assertEqual(missing, [])

    def test_example_result_types_are_preserved(self) -> None:
        actual = {member.name: member.value for member in harness.mod.FetchStatus}
        self.assertEqual({name: actual.get(name) for name in FETCH_STATUS}, FETCH_STATUS)
        for name in ("FetchResult", "ResilienceConfig", "UserProfile", "fetch_user_profile"):
            self.assertTrue(hasattr(harness.mod, name), name)


if __name__ == "__main__":
    unittest.main()
