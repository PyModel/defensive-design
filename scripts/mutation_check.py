#!/usr/bin/env python3
"""Prove the reference checks detect removal of each defensive control.

Each mutant deletes or disables one control in a temporary copy of the repository and
runs the reference checks and unit tests there. A surviving mutant means that control
is untested. Nothing in the working tree is modified.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = Path("skills/defensive-design/references/resilient_http_example.py")
TIMEOUT_S = 300

# name -> (exact source text, replacement). Each source text must occur exactly once.
MUTANTS: dict[str, tuple[str, str]] = {
    "streaming size cap": (
        "        if len(body) + len(chunk) > max_bytes:\n            return None\n",
        "",
    ),
    "network error retry": (
        "            except httpx.NetworkError:\n"
        "                await breaker.record_failure(permit)\n"
        "                probe_resolved = True\n"
        '                retry_error_code = "TRANSPORT_ERROR"\n',
        "",
    ),
    "timeout counted by breaker": (
        "                await breaker.record_failure(permit)\n"
        "                probe_resolved = True\n"
        '                retry_error_code = "UPSTREAM_TIMEOUT"',
        '                probe_resolved = True\n                retry_error_code = "UPSTREAM_TIMEOUT"',
    ),
    "phase timeouts sent": ("                    timeout=config.attempt_timeout(),\n", ""),
    "unresolved probe released": (
        "                if not probe_resolved:\n                    await breaker.release_probe(permit)",
        "                pass",
    ),
    "unsafe text rejected": (
        "    if any(unicodedata.category(ch) in _UNSAFE_TEXT_CATEGORIES for ch in value):\n"
        "        return False\n",
        "",
    ),
    "per-attempt total bound": (
        "async with asyncio.timeout(config.per_attempt_timeout_s), client.stream(",
        "async with client.stream(",
    ),
    "deadline-cut attempt counted": (
        "                if not probe_resolved and loop.time() >= deadline:\n"
        "                    await breaker.record_failure(permit)\n"
        "                    probe_resolved = True\n",
        "",
    ),
    "remaining-budget check": (
        "            if loop.time() + delay >= deadline:\n",
        "            if False:\n",
    ),
    "pool saturation keeps cooldown": (
        "                await breaker.abandon_probe(permit)\n                probe_resolved = True\n",
        "",
    ),
    "garbage is breaker-neutral": (
        "                        else:\n                            await breaker.record_reachable(permit)\n",
        "                        else:\n                            await breaker.record_success(permit)\n",
    ),
    "JSON depth bound": (
        "    if _json_depth_exceeds(text, MAX_JSON_DEPTH):\n",
        "    if False:\n",
    ),
    "late-completion recheck": (
        "            if loop.time() >= deadline:\n                raise TimeoutError\n",
        "",
    ),
}


def run_suites(work: Path) -> bool:
    """Return True when any suite fails, meaning the mutant was detected."""
    commands = (
        [sys.executable, "scripts/verify_reference.py"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
    )
    for command in commands:
        result = subprocess.run(command, cwd=work, capture_output=True, timeout=TIMEOUT_S, check=False)
        if result.returncode != 0:
            return True
    return False


def main() -> int:
    source = (ROOT / EXAMPLE).read_text(encoding="utf-8")
    for name, (old, _) in MUTANTS.items():
        if source.count(old) != 1:
            print(f"ERROR: mutant {name!r} no longer matches the example exactly once", file=sys.stderr)
            return 2
    survivors = []
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp) / "repo"
        shutil.copytree(
            ROOT,
            work,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".venv"),
        )
        # An unmutated copy must pass, or every mutant would look "killed".
        if run_suites(work):
            print("ERROR: unmutated copy fails its checks; fix them first", file=sys.stderr)
            return 2
        for name, (old, new) in MUTANTS.items():
            (work / EXAMPLE).write_text(source.replace(old, new), encoding="utf-8")
            detected = run_suites(work)
            print(f"{'KILLED  ' if detected else 'SURVIVED'} {name}")
            if not detected:
                survivors.append(name)
    if survivors:
        print(f"FAIL: {len(survivors)} of {len(MUTANTS)} mutants survived", file=sys.stderr)
        return 1
    print(f"PASS: all {len(MUTANTS)} mutants killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
