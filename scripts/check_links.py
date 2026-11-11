#!/usr/bin/env python3
"""Fetch every external link in tracked Markdown. Maintainer and CI use; needs network.

Run from the repository root: `python -m scripts.check_links`. A link that answers
404 or 410 fails the run. A site that refuses automated clients, or cannot be reached,
is reported as unverified and does not fail it: that is not evidence the link is dead.
"""
from __future__ import annotations

import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.validate_skill import link_targets, tracked_markdown

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = 20
ATTEMPTS = 2
RETRY_WAIT_S = 3
MAX_LINKS = 300
GONE = {404, 410}


def classify(status: int | None) -> str:
    """ok, broken, or unverified (blocked, server error or unreachable)."""
    if status is None:
        return "unverified"
    if 200 <= status < 400:
        return "ok"
    return "broken" if status in GONE else "unverified"


def fetch_status(url: str) -> int | None:
    request = urllib.request.Request(url, headers={"User-Agent": "link-check"})
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return exc.code
            status: int | None = exc.code
        except (urllib.error.URLError, http.client.HTTPException, ValueError, OSError):
            # Unreachable, a malformed response or a malformed URL: unverified, never a crash.
            status = None
        if attempt + 1 < ATTEMPTS:
            time.sleep(RETRY_WAIT_S)
    return status


def main() -> int:
    files = tracked_markdown(ROOT) or sorted(ROOT.glob("skills/**/*.md"))
    urls = sorted(
        {
            target.split("#", 1)[0]
            for path in files
            for target in link_targets(path.read_text(encoding="utf-8", errors="replace"))
            if target.startswith("https://")
        }
    )
    if len(urls) > MAX_LINKS:
        print(f"ERROR: {len(urls)} links exceed the {MAX_LINKS}-link budget", file=sys.stderr)
        return 2
    broken = 0
    for url in urls:
        status = fetch_status(url)
        verdict = classify(status)
        broken += verdict == "broken"
        if verdict != "ok":
            print(f"{verdict.upper():10} {status} {url}")
    print(f"{len(urls)} links checked, {broken} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
