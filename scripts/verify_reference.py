#!/usr/bin/env python3
"""Self-contained regression checks for the packaged resilient_http_example.py."""

from __future__ import annotations

import asyncio
import gzip
import importlib.util
import inspect
import json
import logging
import pathlib
import sys
from datetime import datetime, timedelta, UTC
from email.utils import format_datetime

import httpx

if not __debug__:
    raise RuntimeError("verify_reference.py requires assertions; do not run with -O")

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "defensive-design" / "references" / "resilient_http_example.py"
spec = importlib.util.spec_from_file_location("resilient_http_example", MODULE_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

KEY = b"0123456789abcdef0123456789abcdef"


class AsyncBytes(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        yield self.content


class ChunkedBytes(httpx.AsyncByteStream):
    """Unread streaming body with no Content-Length, optionally dripped slowly."""

    def __init__(self, chunks: list[bytes], delay_s: float = 0.0):
        self.chunks = chunks
        self.delay_s = delay_s

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            yield chunk


def cfg(**overrides):
    values = {
        "telemetry_key": KEY,
        "expected_origin": "https://example.test",
        "deadline_s": 1.0,
        "per_attempt_timeout_s": 0.25,
        "max_attempts": 3,
        "base_delay_s": 0.001,
        "max_delay_s": 0.002,
        "max_response_bytes": 1024,
    }
    values.update(overrides)
    return mod.ResilienceConfig(**values)


async def run_fetch(
    handler,
    *,
    config=None,
    breaker=None,
    user_id="abc-123_x.y~z",
    base_url="https://example.test",
    **fetch_kwargs,
):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url=base_url, transport=transport) as client:
        return await mod.fetch_user_profile(
            client,
            breaker
            or mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=0.01),
            user_id=user_id,
            request_id="req-1",
            config=config or cfg(),
            **fetch_kwargs,
        )


async def test_success_with_contract_safe_path_segment():
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
    assert observed_path == "/users/abc-123_x.y~z"


async def test_email_domain_is_canonicalized_without_unicode_aliases():
    async def uppercase_handler(request):
        return httpx.Response(
            200,
            json={"display_name": "Alice", "email_domain": "EXAMPLE.COM"},
        )

    result = await run_fetch(uppercase_handler)
    assert result.status is mod.FetchStatus.SUCCESS
    assert result.data is not None
    assert result.data.email_domain == "example.com"

    # Deliberate confusables: ideographic full stop and a fullwidth letter.
    for supplied in ("example。com", "faß.de", "ｅxample.com"):  # noqa: RUF001

        async def handler(request, domain=supplied):
            return httpx.Response(
                200,
                json={"display_name": "Alice", "email_domain": domain},
            )

        result = await run_fetch(handler)
        assert result.status is mod.FetchStatus.INVALID_PAYLOAD
        assert result.error_code == "INVALID_EMAIL_DOMAIN"


async def test_missing_email_domain_preserves_absence():
    async def handler(request):
        return httpx.Response(200, json={"display_name": "Alice"})

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.SUCCESS
    assert result.data is not None
    assert result.data.email_domain is None


async def test_dot_segments_are_rejected_before_io():
    """A path-segment identifier must not normalize outside `/users/`."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    for user_id in (".", ".."):
        try:
            await run_fetch(handler, user_id=user_id)
        except ValueError:
            continue
        raise AssertionError(f"expected dot segment {user_id!r} to be rejected")
    assert calls == 0, calls


async def test_encoded_separator_candidates_are_rejected_before_io():
    """Containment must not depend on downstream percent-decoding behavior."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    for user_id in ("a/b", "a%2fb", "a?b", "a\\b"):
        try:
            await run_fetch(handler, user_id=user_id)
        except ValueError:
            continue
        raise AssertionError(f"expected unsafe segment {user_id!r} to be rejected")
    assert calls == 0, calls


async def test_non_utf8_user_id_is_rejected_before_io():
    """Hostile Unicode must become a stable validation error, not an encoder crash."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    try:
        await run_fetch(handler, user_id="\ud800")
    except ValueError as exc:
        assert type(exc) is ValueError, type(exc)
    else:
        raise AssertionError("expected unpaired surrogate to be rejected")
    assert calls == 0, calls


async def test_log_correlation_id_rejects_control_characters():
    """A logged correlation value must not permit forged log lines."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://example.test", transport=transport
    ) as client:
        try:
            await mod.fetch_user_profile(
                client,
                mod.AsyncCircuitBreaker(),
                user_id="alice",
                request_id="req-1\nforged=true",
                config=cfg(),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("expected unsafe request_id to be rejected")
    assert calls == 0, calls


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
    # The breaker opened because of this call's own failures; report their cause.
    assert result.error_code == "UPSTREAM_TRANSIENT_5XX", result.error_code


async def test_transient_failure_then_success_resets_breaker():
    calls = 0
    breaker = mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=30)

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"display_name": "Alice"})

    result = await run_fetch(handler, breaker=breaker)
    assert calls == 2, calls
    assert result.status is mod.FetchStatus.SUCCESS
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.failure_count == 0


async def test_permanent_5xx_is_not_retried():
    """Only dependency-contract transient statuses belong in the retry set."""
    for status in (501, 505):
        calls = 0

        async def handler(request, _status=status):
            nonlocal calls
            calls += 1
            return httpx.Response(_status)

        result = await run_fetch(handler)
        assert calls == 1, (status, calls)
        assert result.status is mod.FetchStatus.UNEXPECTED_RESPONSE
        assert result.error_code == "UPSTREAM_PERMANENT_5XX"


async def test_malformed_content_encoding_is_rejected_before_decoding():
    """An encoded response is rejected before an unsafe decoder can run."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=AsyncBytes(b"not-a-gzip-stream"),
        )

    result = await run_fetch(handler)
    assert calls == 1, calls
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code == "UNSUPPORTED_CONTENT_ENCODING"


async def test_compressed_body_is_rejected_before_expansion():
    """A small encoded body must not expand before the response-size boundary."""
    accepted_encoding = None
    compressed = gzip.compress(b"x" * 1_000_000)
    assert len(compressed) < 2_048

    async def handler(request):
        nonlocal accepted_encoding
        accepted_encoding = request.headers.get("accept-encoding")
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=AsyncBytes(compressed),
        )

    result = await run_fetch(handler, config=cfg(max_response_bytes=2_048))
    assert accepted_encoding == "identity", accepted_encoding
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code == "UNSUPPORTED_CONTENT_ENCODING"


async def test_pool_timeout_is_shed_not_retried():
    """Retrying local pool saturation would add load without reaching the dependency."""
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.PoolTimeout("pool saturated", request=request)

    result = await run_fetch(handler)
    assert calls == 1, calls
    assert result.status is mod.FetchStatus.OVERLOADED
    assert result.error_code == "LOCAL_POOL_TIMEOUT"


async def test_protocol_errors_are_not_retried_without_a_contract():
    """A protocol defect is terminal unless the dependency contract says otherwise."""
    for error_type in (httpx.LocalProtocolError, httpx.RemoteProtocolError):
        calls = 0

        async def handler(request, _error_type=error_type):
            nonlocal calls
            calls += 1
            raise _error_type("protocol failure", request=request)

        result = await run_fetch(handler)
        assert calls == 1, (error_type, calls)
        assert result.status is mod.FetchStatus.UNEXPECTED_RESPONSE
        assert result.error_code == "NON_RETRYABLE_REQUEST_ERROR"


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
            content=json.dumps(
                {"display_name": "Alice", "email_domain": "example.com"}
            ).encode(),
        )

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.SUCCESS


async def test_deep_json_is_typed_failure():
    # CPython 3.14 parses this without RecursionError; the explicit bound must not
    # depend on interpreter recursion behavior.
    depth = mod.MAX_JSON_DEPTH + 1
    body = ("[" * depth + "0" + "]" * depth).encode()

    async def handler(request):
        return httpx.Response(200, content=body)

    result = await run_fetch(handler, config=cfg(max_response_bytes=len(body) + 10))
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code == "JSON_TOO_DEEP", result.error_code


def test_json_depth_scan_ignores_brackets_inside_strings():
    limit = 2
    assert not mod._json_depth_exceeds('{"a": "[[[[{{{{"}', limit)
    assert not mod._json_depth_exceeds('{"a": "\\"[[[["}', limit)
    assert mod._json_depth_exceeds('{"a": [{"b": 1}]}', limit)


async def test_unsafe_json_forms_are_typed_failures():
    cases = (
        b'{"display_name":"Alice","unused":' + b"9" * 5_000 + b"}",
        b'{"display_name":"Alice","display_name":"Mallory"}',
        b'{"display_name":"Alice","unused":NaN}',
    )
    for body in cases:

        async def handler(request, _body=body):
            return httpx.Response(200, content=_body)

        result = await run_fetch(handler, config=cfg(max_response_bytes=len(body) + 10))
        assert result.status is mod.FetchStatus.INVALID_PAYLOAD
        assert result.error_code == "MALFORMED_JSON"


async def test_invalid_unicode_output_is_rejected():
    cases = (
        (b'{"display_name":"\\ud800"}', "INVALID_DISPLAY_NAME"),
        (
            b'{"display_name":"Alice","email_domain":"\\ud800"}',
            "INVALID_EMAIL_DOMAIN",
        ),
    )
    for body, error_code in cases:

        async def handler(request, _body=body):
            return httpx.Response(200, content=_body)

        result = await run_fetch(handler)
        assert result.status is mod.FetchStatus.INVALID_PAYLOAD
        assert result.error_code == error_code


async def test_operation_deadline_is_hard():
    never = asyncio.Event()

    async def handler(request):
        await never.wait()
        raise AssertionError("unreachable")

    result = await run_fetch(
        handler, config=cfg(deadline_s=0.01, per_attempt_timeout_s=0.01)
    )
    assert result.status is mod.FetchStatus.CANCELLED
    assert result.error_code == "DEADLINE_EXCEEDED"


async def test_caller_cancellation_propagates():
    """Caller cancellation must not be converted into an ordinary failure result."""
    started = asyncio.Event()
    never = asyncio.Event()

    async def handler(request):
        started.set()
        await never.wait()
        raise AssertionError("unreachable")

    task = asyncio.create_task(run_fetch(handler))
    await started.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return
    raise AssertionError("caller cancellation was swallowed")


async def test_half_open_reachable_response_resolves_probe():
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1,
        reset_timeout_s=1.0,
        clock=lambda: now[0],
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    now[0] = 1.0

    async def handler(request):
        # 409 is classified breaker-neutral (record_reachable), not healthy.
        return httpx.Response(409)

    result = await run_fetch(handler, breaker=breaker)
    assert result.status is mod.FetchStatus.UNEXPECTED_RESPONSE
    assert result.error_code == "UNEXPECTED_CLIENT_STATUS"
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.probing is False


async def test_http_statuses_map_to_expected_results():
    cases = {
        404: (mod.FetchStatus.NOT_FOUND, None),
        401: (mod.FetchStatus.UNAUTHENTICATED, "UNAUTHENTICATED"),
        403: (mod.FetchStatus.FORBIDDEN, "FORBIDDEN"),
        429: (mod.FetchStatus.RATE_LIMITED, "RATE_LIMITED"),
        400: (mod.FetchStatus.INVALID_REQUEST, "CLIENT_ERROR"),
        407: (mod.FetchStatus.UNEXPECTED_RESPONSE, "UNEXPECTED_CLIENT_STATUS"),
        409: (mod.FetchStatus.UNEXPECTED_RESPONSE, "UNEXPECTED_CLIENT_STATUS"),
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


async def test_neutral_outcomes_do_not_reset_failure_count():
    """Contract-neutral outcomes must not erase availability failures."""
    breaker = mod.AsyncCircuitBreaker(failure_threshold=3, reset_timeout_s=30)
    for _ in range(3):
        permit = await breaker.allow()
        assert permit is not None
        await breaker.record_failure(permit)
        await breaker.record_reachable(permit)
    assert breaker.state is mod.CircuitState.OPEN, breaker.state
    assert breaker.failure_count == 3, breaker.failure_count


async def test_contract_valid_results_reset_failure_count():
    cases = {
        400: mod.FetchStatus.INVALID_REQUEST,
        401: mod.FetchStatus.UNAUTHENTICATED,
        403: mod.FetchStatus.FORBIDDEN,
        404: mod.FetchStatus.NOT_FOUND,
        429: mod.FetchStatus.RATE_LIMITED,
    }
    for status, expected in cases.items():
        breaker = mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=30)
        permit = await breaker.allow()
        assert permit is not None
        await breaker.record_failure(permit)

        async def handler(request, _status=status):
            return httpx.Response(_status)

        result = await run_fetch(handler, breaker=breaker)
        assert result.status is expected
        assert breaker.failure_count == 0
        assert breaker.state is mod.CircuitState.CLOSED


async def test_neutral_response_during_probe_closes_breaker():
    """A reachable neutral response during HALF_OPEN proves recovery."""
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1,
        reset_timeout_s=1.0,
        clock=lambda: now[0],
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    now[0] = 1.0
    probe = await breaker.allow()
    assert probe is not None
    await breaker.record_reachable(probe)
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.probing is False


async def test_stale_probe_result_is_fenced():
    """An old probe cannot release or resolve a newer probe."""
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1,
        reset_timeout_s=30,
        clock=lambda: now[0],
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    now[0] = 30.0
    old_probe = await breaker.allow()
    assert old_probe is not None
    assert breaker.probing is True

    now[0] = 300.0
    assert await breaker.allow() is None, (
        "time alone must not create overlapping probes"
    )
    await breaker.release_probe(old_probe)
    assert breaker.state is mod.CircuitState.OPEN

    now[0] = 330.0
    new_probe = await breaker.allow()
    assert new_probe is not None and new_probe != old_probe
    await breaker.record_success(old_probe)
    assert breaker.state is mod.CircuitState.HALF_OPEN
    assert breaker.probing is True
    await breaker.record_success(new_probe)
    assert breaker.state is mod.CircuitState.CLOSED
    assert breaker.probing is False


async def test_breaker_recovery_uses_injected_clock():
    """Breaker recovery must be testable without timing sleeps."""
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1,
        reset_timeout_s=5,
        clock=lambda: now[0],
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    assert await breaker.allow() is None
    now[0] = 5.0
    probe = await breaker.allow()
    assert probe is not None
    assert await breaker.allow() is None
    now[0] = 7.0
    assert await breaker.allow() is None
    await breaker.release_probe(probe)
    now[0] = 12.0
    assert await breaker.allow() is not None


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


async def test_client_hooks_are_rejected_before_io():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    async def hook(value):
        return None

    for hook_kind in ("request", "response"):
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://example.test",
            transport=transport,
            event_hooks={hook_kind: [hook]},
        ) as client:
            try:
                await mod.fetch_user_profile(
                    client,
                    mod.AsyncCircuitBreaker(),
                    user_id="alice",
                    request_id="req-1",
                    config=cfg(),
                )
            except ValueError:
                continue
            raise AssertionError(f"expected {hook_kind} hook to be rejected")
    assert calls == 0, calls


async def test_untrusted_dependency_origin_is_rejected_before_io():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"display_name": "Alice"})

    for base_url in ("http://example.test", "https://other.test"):
        try:
            await run_fetch(handler, base_url=base_url)
        except ValueError:
            continue
        raise AssertionError(f"expected untrusted origin {base_url!r} to be rejected")
    assert calls == 0, calls


async def test_429_surfaces_bounded_retry_after():
    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "7"})

    result = await run_fetch(handler)
    assert result.status is mod.FetchStatus.RATE_LIMITED
    assert result.retry_after_s == 7.0, result.retry_after_s


async def test_retry_after_above_budget_is_not_shortened():
    """A local cap must not turn a server minimum into an earlier retry hint."""

    async def handler(request):
        return httpx.Response(429, headers={"retry-after": "99999999"})

    result = await run_fetch(handler, config=cfg(max_retry_after_s=2.0))
    assert result.status is mod.FetchStatus.RATE_LIMITED
    assert result.error_code == "RETRY_AFTER_EXCEEDS_BUDGET"
    assert result.retry_after_s is None


def test_retry_after_parsing():
    parse = mod._parse_retry_after
    # delay-seconds
    assert parse("12", 60).delay_s == 12.0
    assert parse("  12  ", 60).delay_s == 12.0
    # A server minimum above the local budget is rejected, never shortened.
    over = parse("900", 30)
    assert over.delay_s is None and over.exceeds_limit
    # HTTP-date, both directions, under a fixed clock.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    future = parse(
        format_datetime(now + timedelta(seconds=45), usegmt=True), 300, now=now
    )
    assert future.delay_s == 45.0 and not future.exceeds_limit, future
    past = parse(
        format_datetime(now - timedelta(seconds=500), usegmt=True), 300, now=now
    )
    assert past.delay_s is None and not past.exceeds_limit, past
    # rejected outright
    for bad in (None, "", "   ", "not-a-number", "-5", "1.5", "NaN", "inf"):
        hint = parse(bad, 60)
        assert hint.delay_s is None and not hint.exceeds_limit, bad
    # RFC 9110 delay-seconds is 1*DIGIT, ASCII. int() alone accepts all of these.
    for bad in ("+12", "1_2", "\u0661\u0662", "12abc"):
        hint = parse(bad, 60)
        assert hint.delay_s is None and not hint.exceeds_limit, bad
    # A digit string long enough to overflow numeric parsing must reject safely.
    assert parse("9" * 400, 30).exceeds_limit
    assert parse("9" * 100_000, 30).exceeds_limit


async def test_retry_after_above_budget_stops_automatic_retry():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"retry-after": "3600"})

    result = await run_fetch(handler, config=cfg(max_retry_after_s=30.0))
    assert calls == 1, calls
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
    assert result.error_code == "RETRY_AFTER_EXCEEDS_BUDGET"
    assert result.retry_after_s is None


async def test_retry_after_is_honored_over_jitter():
    calls = 0
    sleeps = []
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=2,
        reset_timeout_s=1.0,
        clock=lambda: now[0],
    )

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"retry-after": "1"})

    async def capture_sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    jitter_ranges = []

    def max_jitter(low, high):
        jitter_ranges.append((low, high))
        return high

    result = await run_fetch(
        handler,
        breaker=breaker,
        config=cfg(deadline_s=4.0, max_retry_after_s=2.0),
        sleep=capture_sleep,
        uniform=max_jitter,
    )

    assert calls == 3, calls
    assert result.retry_after_s == 1.0, result.retry_after_s
    assert sleeps == [1.001, 1.002], sleeps
    assert jitter_ranges == [(0.0, 0.001), (0.0, 0.002)], jitter_ranges


async def test_module_logger_uses_pseudonymous_subjects():
    """This module's own records must not contain the raw external identifier."""
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    async def handler(request):
        return httpx.Response(503)

    capture = Capture()
    previous_level = mod.logger.level
    mod.logger.addHandler(capture)
    mod.logger.setLevel(logging.WARNING)
    try:
        await run_fetch(
            handler,
            user_id="secret-canary-user",
            config=cfg(max_attempts=1),
        )
    finally:
        mod.logger.removeHandler(capture)
        mod.logger.setLevel(previous_level)

    rendered = "\n".join(
        f"{record.getMessage()} {record.__dict__!r}" for record in records
    )
    assert records, "expected a retry-exhaustion record"
    assert "secret-canary-user" not in rendered
    assert mod.pseudonymize("secret-canary-user", KEY) in rendered


def test_attempt_timeout_bounds_each_phase_separately():
    timeout = cfg(
        deadline_s=10.0,
        per_attempt_timeout_s=5.0,
        connect_timeout_s=1.0,
        pool_timeout_s=0.5,
    ).attempt_timeout()
    assert (timeout.connect, timeout.pool) == (1.0, 0.5)
    assert (timeout.read, timeout.write) == (5.0, 5.0)
    # Defaults fall back to the per-attempt value.
    fallback = cfg(deadline_s=10.0, per_attempt_timeout_s=3.0).attempt_timeout()
    assert (fallback.connect, fallback.read, fallback.write, fallback.pool) == (
        3.0,
    ) * 4


def test_config_rejects_pathological_values():
    bad: list[dict[str, object]] = [
        {"deadline_s": 1.0, "per_attempt_timeout_s": 2.0},
        {"per_attempt_timeout_s": 0.25, "connect_timeout_s": 0.5},
        {"per_attempt_timeout_s": 0.25, "pool_timeout_s": 0.5},
        {"deadline_s": float("nan")},
        {"base_delay_s": float("inf")},
        {"max_attempts": 1.5},
        {"max_response_bytes": True},
        {"telemetry_key": b"short"},
        {"max_retry_after_s": 0},
        {"connect_timeout_s": -1.0},
        {"pool_timeout_s": float("nan")},
        {"expected_origin": "http://example.test"},
        {"deadline_s": 10**10_000},
        {"max_attempts": 5_000, "base_delay_s": 5e-324},
    ]
    for override in bad:
        try:
            cfg(**override)
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"expected validation error for {override!r}")

    breaker_bad: tuple[dict[str, object], ...] = (
        {"failure_threshold": True},
        {"reset_timeout_s": 10**10_000},
        {"clock": None},
    )
    for override in breaker_bad:
        try:
            mod.AsyncCircuitBreaker(**override)
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"expected breaker validation error for {override!r}")


def test_terminal_status_values_are_unique():
    members = list(mod.FetchStatus.__members__.values())
    assert len(members) == len(set(members)), "FetchStatus contains aliases"
    values = [member.value for member in members]
    assert len(values) == len(set(values)), "FetchStatus values are not unique"


def test_config_repr_redacts_sensitive_fields():
    rendered = repr(cfg())
    assert KEY.decode("ascii") not in rendered, rendered
    assert "example.test" not in rendered, rendered


async def test_retry_after_beyond_remaining_deadline_returns_hint():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, headers={"retry-after": "1"})

    loop = asyncio.get_running_loop()
    started = loop.time()
    result = await run_fetch(handler, config=cfg(deadline_s=0.3))
    assert calls == 1, calls
    assert loop.time() - started < 0.3
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
    assert result.error_code == "UPSTREAM_TRANSIENT_5XX", result.error_code
    assert result.retry_after_s == 1.0, result.retry_after_s


async def test_slow_drip_body_is_bounded_per_attempt():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=ChunkedBytes([b" "] * 50, delay_s=0.01))

    result = await run_fetch(
        handler,
        config=cfg(deadline_s=1.0, per_attempt_timeout_s=0.05, max_attempts=2),
        breaker=mod.AsyncCircuitBreaker(failure_threshold=5, reset_timeout_s=1.0),
    )
    assert calls == 2, calls
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
    assert result.error_code == "UPSTREAM_TIMEOUT", result.error_code


async def test_deadline_cut_attempt_counts_as_breaker_failure():
    never = asyncio.Event()

    async def handler(request):
        await never.wait()
        raise AssertionError("unreachable")

    breaker = mod.AsyncCircuitBreaker(failure_threshold=5, reset_timeout_s=1.0)
    result = await run_fetch(
        handler,
        config=cfg(deadline_s=0.05, per_attempt_timeout_s=0.05),
        breaker=breaker,
    )
    assert result.status is mod.FetchStatus.CANCELLED
    assert breaker.failure_count == 1, breaker.failure_count


async def test_caller_cancellation_releases_probe_without_failure():
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1, reset_timeout_s=1.0, clock=lambda: now[0]
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    now[0] = 1.0
    started = asyncio.Event()
    never = asyncio.Event()

    async def handler(request):
        started.set()
        await never.wait()
        raise AssertionError("unreachable")

    task = asyncio.create_task(run_fetch(handler, breaker=breaker))
    await started.wait()
    assert breaker.probing is True
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("caller cancellation was swallowed")
    assert breaker.state is mod.CircuitState.OPEN
    assert breaker.probing is False
    assert breaker.failure_count == 1, breaker.failure_count


async def test_chunked_body_over_limit_is_bounded_while_streaming():
    async def handler(request):
        return httpx.Response(200, stream=ChunkedBytes([b"x" * 100] * 5))

    result = await run_fetch(handler, config=cfg(max_response_bytes=128))
    assert result.status is mod.FetchStatus.INVALID_PAYLOAD
    assert result.error_code == "RESPONSE_TOO_LARGE"


async def test_transport_errors_are_retried_and_counted():
    for error in (httpx.ConnectError, httpx.ReadTimeout):
        calls = 0

        async def handler(request, error=error):
            nonlocal calls
            calls += 1
            raise error("simulated", request=request)

        breaker = mod.AsyncCircuitBreaker(failure_threshold=5, reset_timeout_s=1.0)
        result = await run_fetch(handler, breaker=breaker)
        assert calls == 3, (error, calls)
        assert breaker.failure_count == 3, (error, breaker.failure_count)
        assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
        expected = "UPSTREAM_TIMEOUT" if error is httpx.ReadTimeout else "TRANSPORT_ERROR"
        assert result.error_code == expected, (error, result.error_code)


async def test_request_carries_configured_phase_timeouts():
    observed = {}

    async def handler(request):
        observed.update(request.extensions["timeout"])
        return httpx.Response(200, json={"display_name": "Alice"})

    config = cfg(per_attempt_timeout_s=0.25, connect_timeout_s=0.1, pool_timeout_s=0.05)
    result = await run_fetch(handler, config=config)
    assert result.status is mod.FetchStatus.SUCCESS
    assert observed == {"connect": 0.1, "read": 0.25, "write": 0.25, "pool": 0.05}, observed


async def test_pool_timeout_during_probe_keeps_cooldown():
    now = [0.0]
    breaker = mod.AsyncCircuitBreaker(
        failure_threshold=1, reset_timeout_s=1.0, clock=lambda: now[0]
    )
    initial = await breaker.allow()
    assert initial is not None
    await breaker.record_failure(initial)
    now[0] = 1.0

    async def handler(request):
        raise httpx.PoolTimeout("simulated", request=request)

    result = await run_fetch(handler, breaker=breaker)
    assert result.status is mod.FetchStatus.OVERLOADED
    assert breaker.state is mod.CircuitState.OPEN
    assert breaker.probing is False
    # The dependency's cooldown was not restarted by our own saturation.
    assert await breaker.allow() is not None


async def test_invalid_payload_does_not_reset_failure_count():
    breaker = mod.AsyncCircuitBreaker(failure_threshold=5, reset_timeout_s=1.0)
    permit = await breaker.allow()
    assert permit is not None
    await breaker.record_failure(permit)

    for response in (
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, content=b"x" * 2048),
        httpx.Response(302),
        httpx.Response(204),
    ):

        async def handler(request, response=response):
            return response

        await run_fetch(handler, breaker=breaker, config=cfg(max_response_bytes=128))
        assert breaker.failure_count == 1, (response.status_code, breaker.failure_count)


async def test_breaker_opened_mid_retry_reports_cause():
    async def handler(request):
        return httpx.Response(503, headers={"retry-after": "0"})

    breaker = mod.AsyncCircuitBreaker(failure_threshold=2, reset_timeout_s=10.0)
    result = await run_fetch(handler, breaker=breaker)
    assert breaker.state is mod.CircuitState.OPEN
    assert result.status is mod.FetchStatus.TEMPORARILY_UNAVAILABLE
    assert result.error_code == "UPSTREAM_TRANSIENT_5XX", result.error_code
    assert result.retry_after_s == 0.0, result.retry_after_s


def test_numeric_headers_are_strict():
    hint = mod._parse_retry_after("0" * 20 + "1", 30.0)
    assert hint == mod._RetryAfterHint(delay_s=1.0), hint
    for raw in ("1_0", "+5", "-1", "\uff15", "1e3", "0x10", "", "9" * 40):
        assert mod._parse_content_length(raw) is None, raw
    assert mod._parse_content_length(" 007 ") == 7
    assert mod._parse_content_length("0") == 0


def test_display_text_rejects_invisible_and_separator_characters():
    for ch in ("\u202e", "\u0085", "\u2028", "\u2029", "\u200b", "\x7f", "\n"):
        assert not mod._is_safe_text(f"Al{ch}ice", 100), repr(ch)
    assert mod._is_safe_text("Alice Ångström", 100)


async def main():
    # Collect every test_* function in definition order so a new check cannot be
    # silently skipped by a hand-maintained list.
    tests = [
        value
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} checks total")


if __name__ == "__main__":
    asyncio.run(main())
