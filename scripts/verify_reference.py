#!/usr/bin/env python3
"""Deterministic regression checks for references/resilient_http_example.py."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys
import time

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
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
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


def test_config_rejects_pathological_values():
    bad = [
        {"deadline_s": float("nan")},
        {"base_delay_s": float("inf")},
        {"max_attempts": 1.5},
        {"max_response_bytes": True},
        {"telemetry_key": b"short"},
    ]
    for override in bad:
        try:
            cfg(**override)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for {override!r}")


async def main():
    test_config_rejects_pathological_values()
    tests = [
        test_success_and_path_encoding,
        test_5xx_opens_breaker_without_content_length_override,
        test_unexpected_201_is_not_5xx,
        test_oversized_200_is_bounded,
        test_malformed_content_length_does_not_escape,
        test_deep_json_is_typed_failure,
        test_operation_deadline_is_hard,
        test_half_open_4xx_resolves_probe,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests) + 1} checks total")


if __name__ == "__main__":
    asyncio.run(main())
