#!/usr/bin/env python3
"""Validate this skill package offline; not a model or general Markdown validator."""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    yaml = None

MAX_FILE_BYTES = 256 * 1024
MAX_MARKDOWN_FILES = 128
MAX_CORE_BYTES = 16 * 1024  # Project budget, not an Agent Skills specification limit.
MAX_CORE_LINES = 500
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
CASE = re.compile(r"test-[0-9]+\Z")
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^\s)]+)\)")
RUBRIC_ID = re.compile(r"^\|\s*(test-[0-9]+)\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)


if yaml is not None:
    class UniqueSafeLoader(yaml.SafeLoader):
        """Safe YAML types with duplicate mapping keys rejected, not overwritten."""

        def construct_mapping(self, node, deep=False):
            self.flatten_mapping(node)
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if key in result:
                    raise ValueError(f"duplicate YAML key: {key!r}")
                result[key] = self.construct_object(value_node, deep=deep)
            return result


def read_text(path: Path, root: Path, issues: list[str]) -> str | None:
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("path escapes package root")
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("file exceeds validation size budget")
        return raw.decode("utf-8")
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        issues.append(f"{path.name}: {exc}")
        return None


def mapping(text: str, label: str, issues: list[str]) -> dict:
    if yaml is None:
        issues.append("PyYAML is required; install the reviewed requirements-dev.txt")
        return {}
    try:
        value = yaml.load(text, Loader=UniqueSafeLoader)
        if not isinstance(value, dict):
            raise ValueError("expected a YAML mapping")
        return value
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        issues.append(f"{label}: invalid YAML: {exc}")
        return {}


def prose(text: str) -> str:
    """Ignore fenced examples when checking this repo's inline links and headings."""
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            lines.append("")
        elif fence is None:
            lines.append(line)
    return "\n".join(lines)


def anchors(text: str) -> set[str]:
    """GitHub-style slugs for this repository's plain ATX headings."""
    result = set()
    counts: Counter[str] = Counter()
    for line in prose(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        slug = re.sub(r"[^\w\- ]", "", match.group(1).lower()).replace(" ", "-")
        suffix = f"-{counts[slug]}" if counts[slug] else ""
        counts[slug] += 1
        result.add(slug + suffix)
    return result


def check_links(path: Path, text: str, root: Path, issues: list[str]) -> set[Path]:
    targets = set()
    for raw in LINK.findall(prose(text)):
        try:
            url = urlsplit(raw)
            if url.scheme in {"https", "http", "mailto"}:
                continue  # Existence and safety of remote content are not established.
            if url.scheme or url.netloc or url.query:
                raise ValueError("unsupported link scheme, authority or local query")
            decoded = unquote(url.path, errors="strict")
            if "\\" in decoded or "\x00" in decoded or Path(decoded).is_absolute():
                raise ValueError("invalid local path")
            target = (path.parent / decoded).resolve() if decoded else path.resolve()
            if not target.is_relative_to(root):
                raise ValueError("local link escapes package root")
            if not target.exists():
                raise ValueError("missing local link target")
            targets.add(target)
            if url.fragment:
                if target.suffix != ".md":
                    raise ValueError("local fragments require a Markdown target")
                body = read_text(target, root, issues)
                if body is not None and unquote(url.fragment) not in anchors(body):
                    raise ValueError("missing local heading anchor")
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            issues.append(f"{path.relative_to(root)}: {raw!r}: {exc}")
    return targets


def validate(root: Path) -> list[str]:
    """Return errors without executing examples, accessing the network, or mutating files."""
    root = root.resolve()
    issues: list[str] = []
    skill_path = root / "SKILL.md"
    skill = read_text(skill_path, root, issues)
    if skill is None:
        return issues
    lines = skill.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        issues.append("SKILL.md: missing closed YAML frontmatter")
        data = {}
    else:
        end = lines.index("---", 1)
        data = mapping("\n".join(lines[1:end]), "SKILL.md", issues)
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if set(data) - allowed:
        issues.append("SKILL.md: unknown frontmatter field")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not NAME.fullmatch(name):
        issues.append("SKILL.md: invalid name")
    elif root.name != name:
        issues.append("SKILL.md: name must match package directory")
    description = data.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024 or not description.strip():
        issues.append("SKILL.md: description must be 1-1024 nonempty characters")
    for field in ("license", "compatibility", "allowed-tools"):
        if field in data and (not isinstance(data[field], str) or not data[field].strip()):
            issues.append(f"SKILL.md: {field} must be a nonempty string")
    if isinstance(data.get("compatibility"), str) and len(data["compatibility"]) > 500:
        issues.append("SKILL.md: compatibility exceeds 500 characters")
    meta = data.get("metadata")
    if not isinstance(meta, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items()):
        issues.append("SKILL.md: this package requires string-valued metadata")
    elif not VERSION.fullmatch(meta.get("version", "")):
        issues.append("SKILL.md: this package requires an x.y.z version string")
    if len(lines) >= MAX_CORE_LINES or len(skill.encode()) > MAX_CORE_BYTES:
        issues.append("SKILL.md: exceeds project core size budget")

    markdown = []
    for path in root.rglob("*.md"):
        if ".git" in path.relative_to(root).parts:
            continue
        markdown.append(path)
        if len(markdown) > MAX_MARKDOWN_FILES:
            issues.append("package exceeds Markdown file validation budget")
            return issues
    direct_targets = set()
    for path in sorted(markdown):
        body = skill if path == skill_path else read_text(path, root, issues)
        if body is not None:
            targets = check_links(path, body, root, issues)
            if path == skill_path:
                direct_targets = targets
    for folder in ("references", "assets"):
        for path in (root / folder).glob("*"):
            if path.suffix in {".md", ".py"} and path.resolve() not in direct_targets:
                issues.append(f"SKILL.md: missing direct link to {path.relative_to(root)}")

    host_path = root / "agents/openai.yaml"
    host_text = read_text(host_path, root, issues)
    if host_text is not None:
        host = mapping(host_text, "agents/openai.yaml", issues)
        interface = host.get("interface")
        if not isinstance(interface, dict):
            issues.append("agents/openai.yaml: missing interface mapping")
        else:
            for key in ("display_name", "short_description", "default_prompt"):
                value = interface.get(key)
                if not isinstance(value, str) or not value.strip():
                    issues.append(f"agents/openai.yaml: invalid {key}")
            prompt = interface.get("default_prompt")
            if isinstance(prompt, str) and isinstance(name, str) and f"${name}" not in prompt:
                issues.append("agents/openai.yaml: default prompt must invoke the skill")

    corpus_text = read_text(root / "evals/defensive-design.prompts.csv", root, issues)
    rubric_text = read_text(root / "evals/behavior-rubric.md", root, issues)
    ids: list[str] = []
    if corpus_text is not None:
        try:
            reader = csv.DictReader(io.StringIO(corpus_text), strict=True)
            if reader.fieldnames != ["id", "should_trigger", "prompt"]:
                issues.append("eval corpus: invalid header")
            classes = set()
            for row in reader:
                ident = row.get("id") or ""
                ids.append(ident)
                if not CASE.fullmatch(ident) or row.get("should_trigger") not in {"true", "false"}:
                    issues.append(f"eval corpus: invalid id or boolean in {ident!r}")
                if None in row or not (row.get("prompt") or "").strip():
                    issues.append(f"eval corpus: missing prompt or extra columns in {ident!r}")
                classes.add(row.get("should_trigger"))
            if classes != {"true", "false"}:
                issues.append("eval corpus: positive and negative coverage required")
            if len(ids) != len(set(ids)):
                issues.append("eval corpus: duplicate case ID")
        except csv.Error as exc:
            issues.append(f"eval corpus: invalid CSV: {exc}")
    if rubric_text is not None:
        rubric_ids = [ident for ident, body in RUBRIC_ID.findall(rubric_text) if body.strip()]
        if len(rubric_ids) != len(set(rubric_ids)):
            issues.append("eval rubric: duplicate case ID")
        if set(rubric_ids) != set(ids):
            issues.append("eval rubric: case IDs must exactly match the corpus")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = validate(args.root)
    for issue in issues:
        print(f"ERROR: {issue}", file=sys.stderr)
    if issues:
        return 1
    print("PASS: skill metadata, local links, host metadata and eval/rubric structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
