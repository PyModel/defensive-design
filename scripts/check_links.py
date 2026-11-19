#!/usr/bin/env python3
"""Bounded external-link sweep; HTTP 404/410 are broken, refusals remain unverified.

Run `python -m scripts.check_links --json report.json`. Each URL runs in a child
process so stuck DNS cannot bypass its deadline. The whole sweep has a scheduling
budget plus a shared one-second child-cleanup grace; no worker survives normal return.
An exit code of zero means no proven broken links, not that every link was verified.
"""
from __future__ import annotations

import argparse
import errno
import http.client
import json
import math
import random
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import sleep as poll_sleep
from urllib.parse import urlsplit

from scripts.validate_skill import link_targets, tracked_markdown

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = 5.0
ATTEMPTS = 2
MAX_LINKS = 300
MAX_URL_BYTES = 4096
GONE = {404, 410}
TRANSIENT = {408, 500, 502, 503, 504}
CLEANUP_S = 1.0


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: int | None
    verdict: str
    reason: str


def classify(status: int | None) -> str:
    """ok, broken, or unverified (blocked, server error or unreachable)."""
    if status is None:
        return "unverified"
    if 200 <= status < 400:
        return "ok"
    return "broken" if status in GONE else "unverified"


def validate_url(url: str) -> None:
    if len(url.encode("utf-8")) > MAX_URL_BYTES or any(ord(char) < 33 or ord(char) == 127 for char in url):
        raise ValueError("link exceeds length budget or contains whitespace/control characters")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("links must be absolute HTTPS URLs without credentials")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("invalid port")


def transient_error(exc: BaseException) -> bool:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, ssl.SSLError):
        return False
    if isinstance(reason, socket.gaierror):
        return reason.errno == socket.EAI_AGAIN
    return isinstance(reason, (TimeoutError, ConnectionError, http.client.RemoteDisconnected)) or (
        isinstance(reason, OSError)
        and reason.errno in {errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.ENETUNREACH,
                             errno.EHOSTUNREACH, errno.EPIPE}
    )


def retry_delay(header: str | None, attempt: int, remaining: float) -> float | None:
    """Honor a bounded Retry-After; decline retries that cannot respect it."""
    delay = random.uniform(0.0, min(1.0, 0.25 * 2**attempt))
    if header is not None:
        try:
            if header.strip().isascii() and header.strip().isdigit():
                requested = float(header.strip())
            else:
                requested = max(0.0, parsedate_to_datetime(header).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            return None
        if not math.isfinite(requested) or requested > 2.0:
            return None
        delay += requested
    return delay if delay < remaining else None


def fetch_status(url: str, *, request_timeout: float = TIMEOUT_S, budget: float = 12.0) -> int | None:
    """Bounded attempts; the caller's child-process deadline also covers DNS."""
    validate_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "defensive-design-link-check"})
    end = time.monotonic() + budget
    status: int | None = None
    for attempt in range(ATTEMPTS):
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        retry_after = None
        try:
            with urllib.request.urlopen(request, timeout=min(request_timeout, remaining)) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            try:
                status = exc.code
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
            finally:
                exc.close()
            if status not in TRANSIENT:
                return status
        except (urllib.error.URLError, http.client.HTTPException, ValueError, OSError) as exc:
            status = None
            if not transient_error(exc):
                return None
        if attempt + 1 < ATTEMPTS:
            delay = retry_delay(retry_after, attempt, end - time.monotonic())
            if delay is None:
                break
            time.sleep(delay)
    return status


def _worker_command(url: str, timeout: float, budget: float) -> list[str]:
    return [sys.executable, "-m", "scripts.check_links", "--worker", url,
            "--request-timeout", str(timeout), "--link-timeout", str(budget)]


def _stop_workers(workers: list[subprocess.Popen[bytes]], *, deadline: float) -> None:
    """Kill first, then reap within one shared grace period, including cancellation."""
    for process in workers:
        if process.poll() is None:
            process.kill()
    cleanup_end = min(deadline, time.monotonic() + CLEANUP_S)
    try:
        for process in workers:
            process.wait(timeout=max(0.0, cleanup_end - time.monotonic()))
    finally:
        for process in workers:
            if process.stdout is not None:
                process.stdout.close()


def _read_result(url: str, process: subprocess.Popen[bytes]) -> LinkResult:
    # The worker writes a single tiny record and has already exited. A bounded read
    # also rejects unexpected output; workers never spawn descendants holding the pipe.
    raw = process.stdout.read(1025) if process.stdout is not None else b""
    status = None
    if process.returncode == 0 and len(raw) <= 1024:
        try:
            data = json.loads(raw)
            value = data["status"]
            if value is None or (type(value) is int and 100 <= value <= 599):
                status = value
                return LinkResult(url, status, classify(status), "http" if status else "unreachable_or_invalid")
        except (ValueError, TypeError, KeyError):
            pass
    return LinkResult(url, None, "unverified", "worker_error")


def check_urls(
    urls: list[str], *, workers: int = 8, budget: float = 90.0,
    link_timeout: float = 12.0, request_timeout: float = TIMEOUT_S,
) -> list[LinkResult]:
    """Every input receives a result, including URLs not started before the deadline."""
    if len(urls) > MAX_LINKS or len(set(urls)) != len(urls):
        raise ValueError("too many links or duplicate URLs")
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    if any(not math.isfinite(value) or not 0 < value <= 600
           for value in (budget, link_timeout, request_timeout)):
        raise ValueError("timeouts must be finite, positive and at most 600 seconds")
    for url in urls:
        validate_url(url)
    end = time.monotonic() + budget
    results: dict[str, LinkResult] = {}
    active: dict[str, tuple[subprocess.Popen[bytes], float]] = {}
    next_index = 0
    try:
        while len(results) < len(urls) and time.monotonic() < end:
            while next_index < len(urls) and len(active) < workers and time.monotonic() < end:
                url = urls[next_index]
                next_index += 1
                expires = min(end, time.monotonic() + link_timeout)
                try:
                    process = subprocess.Popen(
                        _worker_command(url, request_timeout, link_timeout), cwd=ROOT,
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    results[url] = LinkResult(url, None, "unverified", "worker_start_failed")
                else:
                    active[url] = process, expires
            expired = []
            for url, (process, expires) in list(active.items()):
                if time.monotonic() >= expires:
                    expired.append(url)
                elif process.poll() is not None:
                    try:
                        results[url] = _read_result(url, process)
                    finally:
                        _stop_workers([process], deadline=end + CLEANUP_S)
                        del active[url]
            if expired:
                _stop_workers([active[url][0] for url in expired], deadline=end + CLEANUP_S)
                for url in expired:
                    results[url] = LinkResult(url, None, "unverified", "link_deadline")
                    del active[url]
            if active:
                poll_sleep(min(0.02, max(0.0, end - time.monotonic())))
    finally:
        _stop_workers([process for process, _ in active.values()], deadline=end + CLEANUP_S)
    return [results.get(url, LinkResult(url, None, "unverified", "run_deadline")) for url in urls]


def collect_urls(root: Path) -> list[str]:
    files = tracked_markdown(root) or sorted(root.glob("skills/**/*.md"))
    return sorted({
        target.split("#", 1)[0]
        for path in files
        for target in link_targets(path.read_text(encoding="utf-8", errors="replace"))
        if target.startswith("https://")
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=90.0)
    parser.add_argument("--link-timeout", type=float, default=12.0)
    parser.add_argument("--request-timeout", type=float, default=TIMEOUT_S)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json", type=Path, help="write every URL outcome and summary as JSON")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            print(json.dumps({"status": fetch_status(
                args.worker, request_timeout=args.request_timeout, budget=args.link_timeout,
            )}))
            return 0
        start = time.monotonic()
        results = check_urls(collect_urls(ROOT), workers=args.workers, budget=args.budget,
                             link_timeout=args.link_timeout, request_timeout=args.request_timeout)
        counts = {verdict: sum(result.verdict == verdict for result in results)
                  for verdict in ("ok", "broken", "unverified")}
        for result in results:
            if result.verdict != "ok":
                print(f"{result.verdict.upper():10} {result.status} {result.reason} {result.url}")
        print(f"{len(results)} links: {counts['ok']} verified, {counts['broken']} broken, "
              f"{counts['unverified']} unverified")
        if args.json:
            args.json.write_text(json.dumps({"counts": counts, "elapsed_s": round(time.monotonic() - start, 3),
                                            "results": [asdict(result) for result in results]}, indent=2) + "\n",
                                 encoding="utf-8")
        return 1 if counts["broken"] else 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
