"""Seeded generative checks for parsing and validation boundaries.

Each test states a property that must hold for every generated input, not only
"did not raise". The generator is stdlib `random` with a fixed seed, so a failure
reproduces exactly; the printed input is the counterexample.
"""
from __future__ import annotations

import json
import random
import tempfile
import unicodedata
import unittest
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from scripts import validate_skill as validator
from scripts import verify_reference as harness

mod = harness.mod
SEED = 20261102
ROUNDS = 2000
ORIGIN = "https://profiles.example"
NOW = datetime(2026, 1, 1, tzinfo=UTC)

# Characters chosen to hit known edge classes: ASCII and fullwidth digits, signs,
# underscores, path syntax, controls, bidi/zero-width format characters, line and
# paragraph separators, a lone surrogate, and astral code points.
SPECIALS = "0123456789\uff10\uff11\uff12+-_ .~/\\%?#@:[]{}\"'\t\r\n\x00\x7f\u200b\u202e\u2028\u2029\ud800\u00e9\U0001d7d8\U0001f600"


def strings(rng: random.Random, max_len: int = 40) -> str:
    pool = [*SPECIALS, *map(chr, range(0x20, 0x7F))]
    return "".join(rng.choice(pool) for _ in range(rng.randint(0, max_len)))


def digit_strings(rng: random.Random) -> str:
    body = "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 40)))
    return rng.choice(["", " ", "\t"]) + body + rng.choice(["", " ", "\t"])


class RetryAfterProperties(unittest.TestCase):
    def check(self, raw: str | None, max_s: float) -> None:
        hint = mod._parse_retry_after(raw, max_s, now=NOW)
        if hint.exceeds_limit:
            self.assertIsNone(hint.delay_s, raw)
        if hint.delay_s is not None:
            self.assertTrue(0 <= hint.delay_s <= max_s, raw)

    def test_bounded_for_arbitrary_text_digits_and_dates(self) -> None:
        rng = random.Random(SEED)
        for _ in range(ROUNDS):
            max_s = rng.choice([0.5, 1.0, 30.0, 3600.0])
            self.check(strings(rng), max_s)
            digits = digit_strings(rng)
            self.check(digits, max_s)
            seconds = int(digits.strip())
            hint = mod._parse_retry_after(digits, max_s, now=NOW)
            if seconds <= max_s:
                self.assertEqual(hint.delay_s, seconds, digits)
            else:
                self.assertTrue(hint.exceeds_limit, digits)
            offset = timedelta(seconds=rng.uniform(-1e6, 1e9))
            self.check(format_datetime(NOW + offset, usegmt=True), max_s)
        self.check(None, 1.0)

    def test_non_ascii_or_signed_digits_are_never_delays(self) -> None:
        for raw in ("+1", "1_0", "\u0661", "\uff10", "1e3", "-0", "0x10"):
            self.assertIsNone(mod._parse_retry_after(raw, 60.0, now=NOW).delay_s, raw)


class ContentLengthProperties(unittest.TestCase):
    def test_result_is_none_or_the_exact_ascii_value(self) -> None:
        rng = random.Random(SEED)
        for _ in range(ROUNDS):
            for raw in (strings(rng), digit_strings(rng)):
                result = mod._parse_content_length(raw)
                if result is not None:
                    stripped = raw.strip()
                    self.assertTrue(stripped.isascii() and stripped.isdigit(), raw)
                    self.assertEqual(result, int(stripped), raw)
                    self.assertLess(result, 10**18, raw)

    def test_valid_ascii_digits_parse_to_their_value(self) -> None:
        rng = random.Random(SEED)
        for _ in range(ROUNDS):
            raw = digit_strings(rng)
            value = int(raw.strip())
            expected = value if value < 10**18 else None
            self.assertEqual(mod._parse_content_length(raw), expected, raw)


class TextAndIdentifierProperties(unittest.TestCase):
    def test_safe_text_excludes_forging_characters_and_encodes(self) -> None:
        rng = random.Random(SEED)
        for _ in range(ROUNDS):
            value = strings(rng)
            if mod._is_safe_text(value, 30):
                self.assertTrue(1 <= len(value) <= 30, repr(value))
                self.assertFalse(
                    any(unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} for ch in value),
                    repr(value),
                )
                value.encode("utf-8")
        self.assertFalse(mod._is_safe_text("a\ud800", 30))

    def test_accepted_user_id_is_exactly_one_segment_on_the_fixed_origin(self) -> None:
        rng = random.Random(SEED)
        with httpx.Client(base_url=ORIGIN) as client:
            # Dot segments are too rare to rely on random generation.
            seeds = [".", "..", "...", ".a", "~", "%2e%2e"]
            for user_id in seeds + [strings(rng, 12) for _ in range(ROUNDS)]:
                try:
                    mod._validate_user_id(user_id)
                except ValueError:
                    continue
                url = urlsplit(str(client.build_request("GET", f"/users/{user_id}").url))
                self.assertEqual((url.scheme, url.netloc), ("https", "profiles.example"), user_id)
                self.assertEqual(url.path.split("/"), ["", "users", user_id], user_id)
                self.assertEqual((url.query, url.fragment), ("", ""), user_id)

    def test_domain_canonicalization_is_idempotent(self) -> None:
        rng = random.Random(SEED)
        labels = ["a", "B", "x-y", "-bad", "bad-", "1", "é", "a" * 63, "a" * 64, ""]
        for _ in range(ROUNDS):
            candidate = ".".join(rng.choice(labels) for _ in range(rng.randint(1, 5)))
            for value in (candidate, strings(rng)):
                canonical = mod._canonicalize_domain(value)
                if canonical is not None:
                    self.assertEqual(mod._canonicalize_domain(canonical), canonical, value)
                    self.assertEqual(canonical, canonical.lower())
                    self.assertLessEqual(len(canonical), 253)


class JsonDepthProperties(unittest.TestCase):
    def nested(self, rng: random.Random, depth: int) -> object:
        noise = rng.choice(['[{"', '\\"]}', "plain", '"', "\\"])
        value: object = noise
        for _ in range(depth):
            value = [value, noise] if rng.random() < 0.5 else {noise: value}
        return value

    def test_matches_real_container_depth(self) -> None:
        rng = random.Random(SEED)
        limit = 8
        for _ in range(ROUNDS // 4):
            depth = rng.randint(0, limit + 3)
            text = json.dumps(self.nested(rng, depth))
            self.assertEqual(mod._json_depth_exceeds(text, limit), depth > limit, text)


class ValidatorProperties(unittest.TestCase):
    def test_markdown_helpers_never_raise_on_arbitrary_text(self) -> None:
        rng = random.Random(SEED)
        fragments = ["```", "~~~", "`", "[a](", ")", "](b.md#c)", "<a href='x'>", "# h", "\n", "===", "---"]
        for _ in range(ROUNDS // 2):
            text = "".join(rng.choice([*fragments, strings(rng, 8)]) for _ in range(rng.randint(0, 20)))
            issues: list[str] = []
            validator.prose(text, issues, "fuzz")
            validator.anchors(text)
            validator.link_targets(text, issues, "fuzz")

    def test_local_links_never_resolve_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / "root"
            root.mkdir()
            (base / "x.md").write_text("# Outside\n", encoding="utf-8")
            (root / "in.md").write_text("# Inside\n", encoding="utf-8")
            doc = root / "doc.md"
            escapes = ["../x.md", "%2e%2e/x.md", "..%2fx.md", "in.md/../../x.md", str(base / "x.md"), "..\\x.md"]
            body = "\n".join(f"[e]({target})" for target in escapes) + "\n[ok](in.md#inside)\n"
            issues: list[str] = []
            targets = validator.check_links(doc, body, root, issues)
            self.assertEqual(targets, {root / "in.md"})
            self.assertEqual(len(issues), len(escapes), issues)


if __name__ == "__main__":
    unittest.main()
