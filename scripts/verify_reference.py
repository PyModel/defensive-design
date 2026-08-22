#!/usr/bin/env python3
"""Deterministic regression checks for references/resilient_http_example.py."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys
import time
from email.utils import formatdate

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "references" / "resilient_http_example.py"
spec = importlib.util.spec_from_file_location("resilient_http_example", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

KEY = b"0123456789abcdef0123456789abcdef"


def cfg(**overrides):
    values = dict(
        telemetry_key=KEY,
        deadline_s=1.0,
        per_attempt_timeout_s=0.25,
        max_attempts=3,
        base_delay_s=0.001,
        max_delay_s=0.002,
        max_response_bytes=1024,
    )
    values.update(overrides)
    return mod.ResilienceConfig(**values)


async def run_fetch(handler, *, config=None, breaker=None, user_id="abc/123?x=y"):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
        return await mod.fetch_user_profile(
            client,
            breaker or mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=0.01),
            user_id=user_id,
            request_id="req-1",
            config=config or cfg(),
        )


async def test_success_and_path_encoding():
    observed_path = None

    async def handler(request):
        nonlocal observed_path
        observed_path = request.url.raw_path.decode("ascii")
        return httpx.Response(
            200,
            json={"display_name": "Alice", "email_domain": "example.com"},
        )

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.SUCCESS
    assert observed_path == "/users/abc%2F123%3Fx%3Dy"


async def test_5xx_opens_breaker_without_content_length_override():
    calls = 0
    breaker = mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=30)

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"content-length": "9999999"})

    result = await run_fetch(handler, breaker=breaker)
    assert calls == 2, calls
    assert breaker.state is mod.CircuitState.OPEN
    assert breaker.failure_count == 2
    assert result.status is mod.FetchStatus.OVERLOADED
    assert result.error_code == "CIRCUIT_OPEN"


async def test_unexpected_201_is_not_5xx():
    async def handler(request):
        return httpx.Response(201, json={"display_name": "Alice"})

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.UNEXPECTED_RESPONSE
    assert result.error_code == "UNEXPECTED_2XX_STATUS"


async def test_oversized_200_is_bounded():
    async def handler(request):
        return httpx.Response(200, content=b"x" * 2048)

    result = await run_fetch(handler, config=cfg(max_response_bytes=128))
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code == "RESPONSE_TOO_LARGE"


async def test_malformed_content_length_does_not_escape():
    async def handler(request):
        return httpx.Response(
            200,
            headers={"content-length": "not-an-int"},
            content=json.dumps({"display_name": "Alice", "email_domain": "example.com"}).encode(),
        )

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.SUCCESS


async def test_deep_json_is_typed_failure():
    # Deep enough to trigger RecursionError on typical CPython builds, while small in bytes.
    body = ("[" * 2000 + "0" + "]" * 2000).encode()

    async def handler(request):
        return httpx.Response(200, content=body)

    result = await run_fetch(handler, config=cfg(max_response_bytes=len(body) + 10))
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code in {"MALFORMED_JSON", "SCHEMA_VIOLATION"}


async def test_operation_deadline_is_hard():
    async def handler(request):
        await asyncio.sleep(0.2)
        return httpx.Response(200, json={"display_name": "Alice", "email_domain": "example.com"})

    start = time.monotonic()
    result = await run_fetch(handler, config=cfg(deadline_s=0.05, per_attempt_timeout_s=1.0))
    elapsed = time.monotonic() - start
    assert elapsed < 0.15, elapsed
    assert result.status is mod.FetchStatus.CANCELLED
    assert result.error_code == "DEADLINE_EXCEEDED"


async def test_half_open_4xx_resolves_probe():
    breaker = mod.AsyncCircuitBreaker(failure_threshold=1, reset_timeout_s=0.001)
    await breaker.record_failure()
    await asyncio.sleep(0.002)

    async def handler(request):
        return httpx.Response(400)

    result = await run_fetch(handler, breaker=breaker)
    assert result.status is mod.FetchStatus.INVALID_REQUEST
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.probing is False


async def test_every_terminal_status_is_distinct():
    """Outcomes with different default caller behavior must not share a status."""
    cases = {
        404: (mod.FetchStatus.NOT_FOUND, None),
        401: (mod.FetchStatus.UNAUTHENTICATED, "UNAUTHENTICATED"),
        403: (mod.FetchStatus.FORBIDDEN, "FORBIDDEN"),
        429: (mod.FetchStatus.RATE_LIMITED, "RATE_LIMITED"),
        400: (mod.FetchStatus.INVALID_REQUEST, "CLIENT_ERROR"),
        302: (mod.FetchStatus.UNEXPECTED_RESPONSE, "UNEXPECTED_REDIRECT"),
    }
    for code, (want_status, want_code) in cases.items():
        async def handler(request, _c=code):
            return httpx.Response(_c)

        result = await run_fetch(handler)
        assert result.status is want_status, (code, result.status)
        assert result.error_code == want_code, (code, result.error_code)


async def test_408_is_retried_not_reported_as_invalid():
    """RFC 9110 s15.5.9: the client MAY repeat a 408. It is not a permanent `invalid`."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(408)

    result = await run_fetch(handler)
    assert calls == 3, calls
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
    assert result.error_code == "UPSTREAM_REQUEST_TIMEOUT"


async def test_interleaved_4xx_does_not_reset_failure_count():
    """A dependency alternating 5xx and 4xx must still trip the breaker."""
    breaker = mod.AsyncCircuitBreaker(failure_threshold=3, reset_timeout_s=30)
    for _ in range(3):
        await breaker.record_failure()
        await breaker.record_reachable()
    assert breaker.state is mod.CircuitState.OPEN, breaker.state
    assert breaker.failure_count == 3, breaker.failure_count


async def test_4xx_during_probe_still_closes_breaker():
    """A response of any kind during HALF_OPEN proves recovery."""
    breaker = mod.AsyncCircuitBreaker(failure_threshold=1, reset_timeout_s=0.001)
    await breaker.record_failure()
    await asyncio.sleep(0.002)
    assert await breaker.allow() is True
    await breaker.record_reachable()
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.probing is False


async def test_abandoned_probe_is_reclaimed():
    """A probe whose task died before releasing must not wedge the breaker."""
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1, reset_timeout_s=30, probe_timeout_s=0.01
    )
    await breaker.record_failure()
    breaker._opened_at = time.monotonic() - 60  # eligible for a probe
    assert await breaker.allow() is True
    assert breaker.probing is True

    # Simulate cancellation between acquiring and releasing the probe.
    assert await breaker.allow() is False, "a second concurrent probe must be refused"
    await asyncio.sleep(0.012)
    assert await breaker.allow() is True, "stale probe was never reclaimed"


async def test_redirect_following_client_is_rejected():
    """The 3xx branch is only meaningful if the client does not follow redirects."""
    async def handler(request):
        return httpx.Response(200, json={"display_name": "A", "email_domain": "e.com"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://example.test", transport=transport, follow_redirects=True
    ) as client:
        try:
            await mod.fetch_user_profile(
                client,
                mod.AsyncCircuitBreaker(),
                user_id="abc",
                request_id="req-1",
                config=cfg(),
            )
        except ValueError:
            return
    raise AssertionError("expected ValueError for a redirect-following client")


async def test_429_surfaces_bounded_retry_after():
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "7"})

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.RATE_LIMITED
    assert result.retry_after_s == 7.0, result.retry_after_s


async def test_hostile_retry_after_is_clamped():
    """A server may send an arbitrarily large value; it must not stall the caller."""
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "99999999"})

    result = await run_fetch(handler, config=cfg(max_retry_after_s=2.0))
    assert result.retry_after_s == 2.0, result.retry_after_s


def test_retry_after_parsing():
    parse = mod._parse_retry_after
    # delay-seconds
    assert parse("12", 60) == 12.0
    assert parse("  12  ", 60) == 12.0
    # clamped
    assert parse("900", 30) == 30.0
    # HTTP-date, both directions
    future = parse(formatdate(time.time() + 45, usegmt=True), 300)
    assert future is not None and 30 < future < 60, future
    past = parse(formatdate(time.time() - 500, usegmt=True), 300)
    assert past is None, past
    # rejected outright
    for bad in (None, "", "   ", "not-a-number", "-5", "1.5", "NaN", "inf"):
        assert parse(bad, 60) is None, bad


async def test_retry_after_is_honored_over_jitter():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"retry-after": "1"})

    start = time.monotonic()
    result = await run_fetch(
        handler, config=cfg(deadline_s=0.30, max_retry_after_s=0.10)
    )
    elapsed = time.monotonic() - start
    assert calls == 3, calls
    assert result.retry_after_s == 0.10, result.retry_after_s
    # Two sleeps of 0.10 between three attempts; jitter alone would be ~0.002.
    assert elapsed >= 0.20, elapsed


def test_attempt_timeout_bounds_each_phase_separately():
    timeout = cfg(
        per_attempt_timeout_s=5.0, connect_timeout_s=1.0, pool_timeout_s=0.5
    ).attempt_timeout()
    assert (timeout.connect, timeout.pool) == (1.0, 0.5)
    assert (timeout.read, timeout.write) == (5.0, 5.0)
    # Defaults fall back to the per-attempt value.
    fallback = cfg(per_attempt_timeout_s=3.0).attempt_timeout()
    assert (fallback.connect, fallback.read, fallback.write, fallback.pool) == (3.0,) * 4


def test_config_rejects_pathological_values():
    bad = [
        {"deadline_s": float("nan")},
        {"base_delay_s": float("inf")},
        {"max_attempts": 1.5},
        {"max_response_bytes": True},
        {"telemetry_key": b"short"},
        {"max_retry_after_s": 0},
        {"connect_timeout_s": -1.0},
        {"pool_timeout_s": float("nan")},
    ]
    for override in bad:
        try:
            cfg(**override)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for {override!r}")


async def main():
    test_config_rejects_pathological_values()
    test_retry_after_parsing()
    test_attempt_timeout_bounds_each_phase_separately()
    tests = [
        test_success_and_path_encoding,
        test_5xx_opens_breaker_without_content_length_override,
        test_unexpected_201_is_not_5xx,
        test_oversized_200_is_bounded,
        test_malformed_content_length_does_not_escape,
        test_deep_json_is_typed_failure,
        test_operation_deadline_is_hard,
        test_half_open_4xx_resolves_probe,
        test_every_terminal_status_is_distinct,
        test_408_is_retried_not_reported_as_invalid,
        test_interleaved_4xx_does_not_reset_failure_count,
        test_4xx_during_probe_still_closes_breaker,
        test_abandoned_probe_is_reclaimed,
        test_redirect_following_client_is_rejected,
        test_429_surfaces_bounded_retry_after,
        test_hostile_retry_after_is_clamped,
        test_retry_after_is_honored_over_jitter,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests) + 3} checks total")


if __name__ == "__main__":
    asyncio.run(main())
