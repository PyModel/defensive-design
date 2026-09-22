#!/usr/bin/env python3
"""Validate this repository's skill packages offline; not a model or general Markdown validator.

Layout: every `skills/<name>/SKILL.md` is an installable package. Maintainer material
(`evals/`, `scripts/`, `tests/`, `tasks/`) lives at the repository root and is never
installed. Checks follow the Agent Skills specification plus documented host rules.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter, deque
from pathlib import Path
from urllib.parse import unquote, urlsplit

from types import ModuleType

yaml_module: ModuleType | None
try:
    import yaml

    yaml_module = yaml
except ImportError:  # Reported as an actionable validation error, not a traceback.
    yaml_module = None

MAX_FILE_BYTES = 256 * 1024
MAX_PACKAGE_FILES = 128
MAX_CORE_BYTES = 16 * 1024  # Project budget, not an Agent Skills specification limit.
MAX_CORE_LINES = 500
MIN_NEGATIVE_SHARE = 0.2  # Project floor so trigger precision stays measurable.
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
RESERVED_NAME_WORDS = ("anthropic", "claude")  # Claude platform rule.
XML_TAG = re.compile(r"<\s*/?\s*[A-Za-z][\w:.-]*(?:\s[^<>]*)?/?\s*>")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
CASE = re.compile(r"test-[0-9]+\Z")
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]*>|[^\s)]+)(?:\s+\"[^\"\n]*\")?\s*\)")
REFERENCE_DEFINITION = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)", re.MULTILINE)
HTML_LINK = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
RUBRIC_ID = re.compile(r"^\|\s*(test-[0-9]+)\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)
NEGATIVE_RUBRIC_PREFIX = "Does not invoke the skill"
# Files a host reads without a Markdown link from SKILL.md.
UNLINKED_PACKAGE_FILES = {"SKILL.md", "LICENSE", "agents/openai.yaml"}
HOST_KEYS = {
    "interface": {
        "display_name",
        "short_description",
        "icon_small",
        "icon_large",
        "brand_color",
        "default_prompt",
    },
    "policy": {"allow_implicit_invocation"},
    "dependencies": {"tools"},
}


if yaml_module is not None:
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


def label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


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
        issues.append(f"{label(path, root)}: {exc}")
        return None


def mapping(text: str, name: str, issues: list[str]) -> dict:
    if yaml_module is None:
        issues.append("PyYAML is required; install the reviewed requirements-dev.txt")
        return {}
    try:
        value = yaml.load(text, Loader=UniqueSafeLoader)
        if not isinstance(value, dict):
            raise ValueError("expected a YAML mapping")
        return value
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        issues.append(f"{name}: invalid YAML: {exc}")
        return {}


def prose(text: str, issues: list[str] | None = None, name: str = "") -> str:
    """Blank fenced blocks and inline code so examples are not parsed as links."""
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = None  # A closing fence carries no info string.
            lines.append("")
        elif fence is None:
            lines.append(CODE_SPAN.sub("", line))
        else:
            lines.append("")
    if fence is not None and issues is not None:
        issues.append(f"{name}: unclosed code fence hides the rest of the file")
    return "\n".join(lines)


def anchors(text: str) -> set[str]:
    """GitHub-style slugs for ATX and setext headings."""
    result = set()
    counts: Counter[str] = Counter()
    lines = prose(text).splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        heading = match.group(1) if match else None
        if (
            heading is None
            and index + 1 < len(lines)
            and line.strip()
            and re.fullmatch(r"\s{0,3}(=+|-+)\s*", lines[index + 1])
        ):
            heading = line.strip()
        if heading is None:
            continue
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        suffix = f"-{counts[slug]}" if counts[slug] else ""
        counts[slug] += 1
        result.add(slug + suffix)
    return result


def link_targets(text: str, issues: list[str] | None = None, name: str = "") -> list[str]:
    body = prose(text, issues, name)
    raw = INLINE_LINK.findall(body) + REFERENCE_DEFINITION.findall(body) + HTML_LINK.findall(body)
    return [value[1:-1] if value.startswith("<") and value.endswith(">") else value for value in raw]


def check_links(path: Path, text: str, root: Path, issues: list[str]) -> set[Path]:
    targets = set()
    for raw in link_targets(text, issues, label(path, root)):
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
            issues.append(f"{label(path, root)}: {raw!r}: {exc}")
    return targets


def check_frontmatter(skill: str, package: Path, issues: list[str]) -> dict:
    lines = skill.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        issues.append("SKILL.md: missing closed YAML frontmatter")
        return {}
    end = lines.index("---", 1)
    data = mapping("\n".join(lines[1:end]), "SKILL.md", issues)
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if set(data) - allowed:
        issues.append("SKILL.md: unknown frontmatter field")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not NAME.fullmatch(name):
        issues.append("SKILL.md: invalid name")
    else:
        if package.name != name:
            issues.append("SKILL.md: name must match package directory")
        if any(word in name for word in RESERVED_NAME_WORDS):
            issues.append("SKILL.md: name contains a reserved word")
    description = data.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024 or not description.strip():
        issues.append("SKILL.md: description must be 1-1024 nonempty characters")
    elif XML_TAG.search(description):
        issues.append("SKILL.md: description must not contain XML tags")
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
    return data


def check_host_metadata(package: Path, name: object, issues: list[str]) -> None:
    host_path = package / "agents/openai.yaml"
    if not host_path.exists():
        return  # Optional host adapter.
    host_text = read_text(host_path, package, issues)
    if host_text is None:
        return
    host = mapping(host_text, "agents/openai.yaml", issues)
    for key in set(host) - set(HOST_KEYS):
        issues.append(f"agents/openai.yaml: unknown top-level key {key!r}")
    for section, keys in HOST_KEYS.items():
        value = host.get(section)
        if value is None:
            continue
        if not isinstance(value, dict):
            issues.append(f"agents/openai.yaml: {section} must be a mapping")
            continue
        for key in set(value) - keys:
            issues.append(f"agents/openai.yaml: unknown {section} key {key!r}")
    interface = host.get("interface")
    if isinstance(interface, dict):
        for key in HOST_KEYS["interface"] & set(interface):
            if not isinstance(interface[key], str) or not interface[key].strip():
                issues.append(f"agents/openai.yaml: invalid {key}")
        prompt = interface.get("default_prompt")
        if (
            isinstance(prompt, str)
            and isinstance(name, str)
            and not re.search(rf"\${re.escape(name)}(?![a-z0-9-])", prompt)
        ):
            issues.append("agents/openai.yaml: default prompt must invoke the skill")
    policy = host.get("policy")
    if (
        isinstance(policy, dict)
        and "allow_implicit_invocation" in policy
        and not isinstance(policy["allow_implicit_invocation"], bool)
    ):
        issues.append("agents/openai.yaml: allow_implicit_invocation must be a boolean")


def package_files(package: Path, issues: list[str]) -> list[Path]:
    files = []
    for path in sorted(package.rglob("*")):
        relative = path.relative_to(package)
        if any(part in {".git", "__pycache__"} for part in relative.parts) or path.is_dir():
            continue
        files.append(path)
    if len(files) > MAX_PACKAGE_FILES:
        issues.append("package exceeds file validation budget")
        return files[:MAX_PACKAGE_FILES]
    return files


def validate_package(package: Path) -> tuple[list[str], str | None]:
    """Return errors for one installable package and its declared name."""
    package = package.resolve()
    issues: list[str] = []
    skill_path = package / "SKILL.md"
    skill = read_text(skill_path, package, issues)
    if skill is None:
        return issues, None
    data = check_frontmatter(skill, package, issues)
    name = data.get("name")

    files = package_files(package, issues)
    links: dict[Path, set[Path]] = {}
    for path in files:
        if path.suffix == ".md":
            body = skill if path == skill_path.resolve() else read_text(path, package, issues)
            if body is not None:
                links[path.resolve()] = check_links(path, body, package, issues)

    direct = links.get(skill_path.resolve(), set())
    for folder in ("references", "assets", "scripts"):
        for path in sorted((package / folder).glob("*")):
            if path.is_file() and path.resolve() not in direct:
                issues.append(f"SKILL.md: missing direct link to {label(path, package)}")

    reachable = {skill_path.resolve()}
    queue = deque([skill_path.resolve()])
    while queue:
        for target in links.get(queue.popleft(), set()):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    for path in files:
        relative = label(path, package)
        if relative not in UNLINKED_PACKAGE_FILES and path.resolve() not in reachable:
            issues.append(f"{relative}: not reachable from SKILL.md; move maintainer files out of the package")

    check_host_metadata(package, name, issues)
    return issues, name if isinstance(name, str) else None


def validate_evals(root: Path, name: str, issues: list[str]) -> None:
    """Maintainer evaluation corpus at `<root>/evals`, paired with its rubric."""
    corpus_text = read_text(root / "evals" / f"{name}.prompts.csv", root, issues)
    rubric_text = read_text(root / "evals" / "behavior-rubric.md", root, issues)
    triggers: dict[str, str] = {}
    if corpus_text is not None:
        try:
            reader = csv.DictReader(io.StringIO(corpus_text), strict=True)
            if reader.fieldnames != ["id", "should_trigger", "prompt"]:
                issues.append("eval corpus: invalid header")
            prompts: Counter[str] = Counter()
            ids: list[str] = []
            for row in reader:
                ident = row.get("id") or ""
                ids.append(ident)
                if not CASE.fullmatch(ident) or row.get("should_trigger") not in {"true", "false"}:
                    issues.append(f"eval corpus: invalid id or boolean in {ident!r}")
                if None in row or not (row.get("prompt") or "").strip():
                    issues.append(f"eval corpus: missing prompt or extra columns in {ident!r}")
                prompts[" ".join((row.get("prompt") or "").split()).lower()] += 1
                triggers[ident] = row.get("should_trigger") or ""
            if len(ids) != len(set(ids)):
                issues.append("eval corpus: duplicate case ID")
            if any(count > 1 for count in prompts.values()):
                issues.append("eval corpus: duplicate prompt")
            negatives = sum(value == "false" for value in triggers.values())
            if not ids or negatives == 0 or negatives == len(ids):
                issues.append("eval corpus: positive and negative coverage required")
            elif negatives / len(ids) < MIN_NEGATIVE_SHARE:
                issues.append(f"eval corpus: negative cases below {MIN_NEGATIVE_SHARE:.0%}")
        except csv.Error as exc:
            issues.append(f"eval corpus: invalid CSV: {exc}")
    if rubric_text is not None:
        rows = [(ident, body) for ident, body in RUBRIC_ID.findall(rubric_text) if body.strip()]
        rubric_ids = [ident for ident, _ in rows]
        if len(rubric_ids) != len(set(rubric_ids)):
            issues.append("eval rubric: duplicate case ID")
        if set(rubric_ids) != set(triggers):
            issues.append("eval rubric: case IDs must exactly match the corpus")
        for ident, body in rows:
            says_negative = body.startswith(NEGATIVE_RUBRIC_PREFIX)
            if ident in triggers and says_negative != (triggers[ident] == "false"):
                issues.append(f"eval rubric: {ident} polarity disagrees with should_trigger")


def validate(root: Path) -> list[str]:
    """Return errors without executing examples, accessing the network, or mutating files."""
    root = root.resolve()
    issues: list[str] = []
    packages = sorted(path.parent for path in (root / "skills").glob("*/SKILL.md"))
    if not packages:
        return ["skills/: no skills/<name>/SKILL.md package found"]
    license_path = root / "LICENSE"
    for package in packages:
        package_issues, name = validate_package(package)
        prefix = label(package, root)
        issues.extend(f"{prefix}/{issue}" for issue in package_issues)
        packaged_license = package / "LICENSE"
        if license_path.exists() and (
            not packaged_license.exists()
            or packaged_license.read_bytes() != license_path.read_bytes()
        ):
            issues.append(f"{prefix}/LICENSE: must be an identical copy of the repository LICENSE")
        if name is not None:
            validate_evals(root, name, issues)
    check_repository_docs(root, issues)
    return issues


def check_repository_docs(root: Path, issues: list[str]) -> None:
    """Check local links in maintainer Markdown outside the installable packages."""
    skipped = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
    docs = [
        path
        for path in sorted(root.rglob("*.md"))
        if not skipped.intersection(path.relative_to(root).parts)
        and path.relative_to(root).parts[0] != "skills"
    ]
    if len(docs) > MAX_PACKAGE_FILES:
        issues.append("repository exceeds Markdown validation budget")
        docs = docs[:MAX_PACKAGE_FILES]
    for path in docs:
        body = read_text(path, root, issues)
        if body is not None:
            check_links(path, body, root, issues)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = validate(args.root)
    for issue in issues:
        print(f"ERROR: {issue}", file=sys.stderr)
    if issues:
        return 1
    print("PASS: package metadata, reachability, local links, host metadata and eval structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
