"""Illustrative defensive outbound HTTP GET pattern.

This example intentionally demonstrates only mechanisms that are relevant to a
read-only HTTP lookup: strict configuration/input validation, a cooperative operation
deadline, bounded/capped retry with full jitter, a small async circuit breaker,
bounded response streaming, typed outcomes, contract-safe path segments, and redacted
identifier logging by this module.

It deliberately does not invent a metrics/tracing stack. Production callers
should integrate with their existing telemetry system. HTTP client, proxy, and
server access logs may record request paths; use non-sensitive opaque path identifiers
or configure those separate logging boundaries to suppress or redact them.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Generic, TypeGuard, TypeVar

import httpx

logger = logging.getLogger(__name__)
T = TypeVar("T")
RETRYABLE_HTTP_STATUSES = frozenset({502, 503, 504})
MAX_RETRY_ATTEMPTS = 10


def _validate_positive_finite(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    try:
        numeric = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be a finite, positive number") from None
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a finite, positive number")


@dataclass(frozen=True, kw_only=True)
class ResilienceConfig:
    """Validated operational policy for the example client."""

    telemetry_key: bytes = field(repr=False)
    expected_origin: str = field(repr=False)
    deadline_s: float = 5.0
    per_attempt_timeout_s: float = 2.0
    max_attempts: int = 3
    base_delay_s: float = 0.2
    max_delay_s: float = 2.0
    max_response_bytes: int = 1_000_000
    # httpx applies a bare float to connect, read, write, and pool alike. These
    # let the slow phases be bounded separately; None means "use the per-attempt
    # value". httpx cannot split the TLS handshake from connect, so that clause
    # of the checklist is not applicable here.
    connect_timeout_s: float | None = None
    pool_timeout_s: float | None = None
    # A server may send an arbitrarily large or far-future Retry-After. Reject
    # automatic retry above this bound; never shorten the server's minimum.
    max_retry_after_s: float = 30.0

    def __post_init__(self) -> None:
        for name, value in (
            ("deadline_s", self.deadline_s),
            ("per_attempt_timeout_s", self.per_attempt_timeout_s),
            ("base_delay_s", self.base_delay_s),
            ("max_delay_s", self.max_delay_s),
            ("max_retry_after_s", self.max_retry_after_s),
            ("connect_timeout_s", self.effective_connect_timeout_s),
            ("pool_timeout_s", self.effective_pool_timeout_s),
        ):
            _validate_positive_finite(name, value)

        if isinstance(self.max_attempts, bool) or not isinstance(
            self.max_attempts, int
        ):
            raise TypeError("max_attempts must be an integer")
        if not 1 <= self.max_attempts <= MAX_RETRY_ATTEMPTS:
            raise ValueError(f"max_attempts must be between 1 and {MAX_RETRY_ATTEMPTS}")

        if isinstance(self.max_response_bytes, bool) or not isinstance(
            self.max_response_bytes, int
        ):
            raise TypeError("max_response_bytes must be an integer")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1")

        if self.base_delay_s > self.max_delay_s:
            raise ValueError("base_delay_s cannot exceed max_delay_s")

        if not isinstance(self.telemetry_key, bytes) or len(self.telemetry_key) < 16:
            raise ValueError("telemetry_key must be at least 16 bytes")

        try:
            origin = httpx.URL(self.expected_origin)
        except (TypeError, httpx.InvalidURL):
            raise ValueError("expected_origin must be a valid HTTPS origin") from None
        if (
            origin.scheme != "https"
            or not origin.host
            or origin.username
            or origin.password
            or origin.path != "/"
            or origin.query
            or origin.fragment
        ):
            raise ValueError("expected_origin must be a credential-free HTTPS origin")

    @property
    def effective_connect_timeout_s(self) -> float:
        return (
            self.per_attempt_timeout_s
            if self.connect_timeout_s is None
            else self.connect_timeout_s
        )

    @property
    def effective_pool_timeout_s(self) -> float:
        return (
            self.per_attempt_timeout_s
            if self.pool_timeout_s is None
            else self.pool_timeout_s
        )

    def attempt_timeout(self) -> httpx.Timeout:
        """Bound each phase separately rather than reusing one value for all four."""
        return httpx.Timeout(
            self.per_attempt_timeout_s,
            connect=self.effective_connect_timeout_s,
            pool=self.effective_pool_timeout_s,
        )


class FetchStatus(Enum):
    """Caller-visible results this operation can actually reach.

    The trailing comment names the relevant result or cause label from
    `references/failure-taxonomy.md`. Results with different caller behavior
    must not share a status value.
    """

    SUCCESS = "success"
    NOT_FOUND = "not_found"  # absence
    INVALID_REQUEST = "invalid_request"  # invalid
    UNAUTHENTICATED = "unauthenticated"  # unauthenticated
    FORBIDDEN = "forbidden"  # unauthorized
    RATE_LIMITED = "rate_limited"  # policy_limit (caller quota)
    INVALID_PAYLOAD = "invalid_payload"  # invalid (dependency output)
    UNEXPECTED_RESPONSE = "unexpected_response"  # permanent_dependency
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"  # transient_dependency
    OVERLOADED = "overloaded"  # overloaded (local pool saturation)
    CANCELLED = "cancelled"  # cancelled (deadline expiry)
    INTERNAL_ERROR = "internal_error"  # invariant_violation


@dataclass(frozen=True)
class _RetryAfterHint:
    delay_s: float | None = None
    exceeds_limit: bool = False


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    display_name: str
    email_domain: str | None


@dataclass(frozen=True)
class FetchResult(Generic[T]):
    status: FetchStatus
    data: T | None = None
    error_code: str | None = None
    retry_after_s: float | None = None


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """Single-event-loop task-safe breaker with a fenced HALF_OPEN probe.

    Counting semantics are *consecutive*: `record_success` resets the counter,
    `record_failure` increments it, and `record_reachable` is deliberately
    neutral while CLOSED. The caller classifies outcomes from its dependency
    contract: valid absence or policy denial can be healthy; status families
    alone do not decide breaker behavior.

    Every allowed call receives a generation permit. Opening or resolving the
    breaker advances the generation, so a late result cannot mutate newer
    state. Time alone never creates an overlapping probe; an unresolved probe
    must be released in `finally`, which reopens the breaker for another bounded
    cooldown.

    This is intentionally small and illustrative. Prefer a proven platform or
    client-library breaker when one already exists and satisfies the contract.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(failure_threshold, bool) or not isinstance(
            failure_threshold, int
        ):
            raise TypeError("failure_threshold must be an integer")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        _validate_positive_finite("reset_timeout_s", reset_timeout_s)
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.failure_threshold = failure_threshold
        self.reset_timeout_s = float(reset_timeout_s)
        self._clock = clock
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._probing = False
        self._generation = 1
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    @property
    def probing(self) -> bool:
        return self._probing

    async def allow(self) -> int | None:
        async with self._lock:
            now = self._clock()
            if self._state is CircuitState.OPEN:
                if now - self._opened_at < self.reset_timeout_s:
                    return None
                self._state = CircuitState.HALF_OPEN
                self._probing = True
                self._generation += 1
                return self._generation

            if self._state is CircuitState.HALF_OPEN:
                return None

            return self._generation

    async def record_success(self, permit: int) -> None:
        """Dependency answered with a contract-defined healthy outcome."""
        async with self._lock:
            if permit != self._generation:
                return
            self._failures = 0
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._probing = False
                self._generation += 1

    async def record_reachable(self, permit: int) -> None:
        """Dependency answered with a contract-defined breaker-neutral result.

        While CLOSED this leaves the failure count untouched. During the active
        HALF_OPEN probe, any response proves reachability and closes the breaker.
        """
        async with self._lock:
            if permit != self._generation:
                return
            if self._state is CircuitState.HALF_OPEN:
                self._failures = 0
                self._state = CircuitState.CLOSED
                self._probing = False
                self._generation += 1

    async def record_failure(self, permit: int) -> None:
        """Dependency had a contract-defined transient availability failure."""
        async with self._lock:
            if permit != self._generation:
                return
            was_half_open = self._state is CircuitState.HALF_OPEN
            if self._state not in {CircuitState.CLOSED, CircuitState.HALF_OPEN}:
                return
            self._failures += 1
            if self._failures >= self.failure_threshold or was_half_open:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._probing = False
                self._generation += 1

    async def release_probe(self, permit: int) -> None:
        """Fence an unresolved probe and restart the open cooldown."""
        async with self._lock:
            if permit == self._generation and self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._probing = False
                self._generation += 1


def pseudonymize(identifier: str, key: bytes) -> str:
    return hmac.new(key, identifier.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _validate_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not (1 <= len(user_id) <= 128):
        raise ValueError("user_id must be a string between 1 and 128 characters")
    if user_id in {".", ".."}:
        raise ValueError("user_id must not be a dot path segment")
    if not all(ch.isascii() and (ch.isalnum() or ch in "-._~") for ch in user_id):
        raise ValueError("user_id must contain only ASCII unreserved path characters")


def _validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or not (1 <= len(request_id) <= 128):
        raise ValueError("request_id must be a string between 1 and 128 characters")
    if not all(ch.isascii() and (ch.isalnum() or ch in "-._:") for ch in request_id):
        raise ValueError("request_id must be an opaque ASCII correlation identifier")


def _parse_retry_after(
    value: str | None,
    max_s: float,
    *,
    now: datetime | None = None,
) -> _RetryAfterHint:
    """Parse a Retry-After header without shortening the server's minimum.

    RFC 9110 s10.2.3 permits `delay-seconds` or an HTTP-date, and sets no upper
    bound, so an HTTP-date can be arbitrarily far in the future. Unparseable,
    negative, or non-finite input is discarded. A valid minimum
    above `max_s` is marked unusable so the caller stops automatic retries
    instead of retrying earlier than the server allowed.
    """
    if value is None:
        return _RetryAfterHint()
    raw = value.strip()
    if not raw:
        return _RetryAfterHint()

    if raw.isascii() and raw.isdigit():
        # `delay-seconds = 1*DIGIT`, ASCII only. int() alone is too permissive:
        # it accepts "+12", "1_2", and non-ASCII digits.
        #
        # Bound the digit string before converting. float() of a long enough
        # integer raises OverflowError, and int() itself refuses more than
        # 4300 digits - either one would be an uncaught crash triggered by a
        # header we do not control. Anything this long is certainly past the
        # limit, so it is rejected without constructing an enormous integer.
        if len(raw) > 18:
            return _RetryAfterHint(exceeds_limit=True)
        seconds = float(int(raw))
        if seconds > max_s:
            return _RetryAfterHint(exceeds_limit=True)
        return _RetryAfterHint(delay_s=seconds)

    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return _RetryAfterHint()
    if when is None:
        return _RetryAfterHint()
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    try:
        current = datetime.now(timezone.utc) if now is None else now
        seconds = (when - current).total_seconds()
    except (OverflowError, OSError, TypeError):
        return _RetryAfterHint()

    if not math.isfinite(seconds) or seconds < 0:
        return _RetryAfterHint()
    if seconds > max_s:
        return _RetryAfterHint(exceeds_limit=True)
    return _RetryAfterHint(delay_s=seconds)


def _parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


async def _read_bounded_body(resp: httpx.Response, max_bytes: int) -> bytes | None:
    declared = _parse_content_length(resp.headers.get("content-length"))
    if declared is not None and declared > max_bytes:
        return None

    if resp.is_stream_consumed:
        return resp.content if len(resp.content) <= max_bytes else None

    body = bytearray()
    async for chunk in resp.aiter_raw():
        if len(body) + len(chunk) > max_bytes:
            return None
        body.extend(chunk)
    return bytes(body)


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON constants are not allowed")


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _is_safe_text(value: object, max_chars: int) -> TypeGuard[str]:
    if not isinstance(value, str) or not (1 <= len(value) <= max_chars):
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _canonicalize_domain(value: object) -> str | None:
    if not _is_safe_text(value, 253):
        return None
    # This dependency-free example intentionally accepts only the DNS LDH subset.
    # Unicode domains require one reviewed IDNA2008/UTS #46 canonicalizer shared by
    # every policy, cache, resolver, and transport boundary; stdlib IDNA2003 can
    # otherwise collapse distinct names such as `faß.de` and `fass.de`.
    if not value.isascii():
        return None
    ascii_domain = value.lower()
    if len(ascii_domain) > 253:
        return None
    labels = ascii_domain.split(".")
    if not all(
        1 <= len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in label)
        for label in labels
    ):
        return None
    return ascii_domain


def _parse_profile(body: bytes, user_id: str) -> FetchResult[UserProfile]:
    try:
        payload = json.loads(
            body.decode("utf-8"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        return FetchResult(
            status=FetchStatus.INVALID_PAYLOAD, error_code="MALFORMED_JSON"
        )

    if not isinstance(payload, dict):
        return FetchResult(
            status=FetchStatus.INVALID_PAYLOAD, error_code="SCHEMA_VIOLATION"
        )

    display_name = payload.get("display_name")
    raw_email_domain = payload.get("email_domain")
    email_domain = (
        None if raw_email_domain is None else _canonicalize_domain(raw_email_domain)
    )

    if not _is_safe_text(display_name, 100):
        return FetchResult(
            status=FetchStatus.INVALID_PAYLOAD, error_code="INVALID_DISPLAY_NAME"
        )
    if raw_email_domain is not None and email_domain is None:
        return FetchResult(
            status=FetchStatus.INVALID_PAYLOAD, error_code="INVALID_EMAIL_DOMAIN"
        )

    return FetchResult(
        status=FetchStatus.SUCCESS,
        data=UserProfile(
            user_id=user_id, display_name=display_name, email_domain=email_domain
        ),
    )


async def fetch_user_profile(
    client: httpx.AsyncClient,
    breaker: AsyncCircuitBreaker,
    *,
    user_id: str,
    request_id: str,
    config: ResilienceConfig,
) -> FetchResult[UserProfile]:
    """Fetch a user profile under one cooperative operation deadline.

    Async cancellation cannot preempt synchronous parsing, logging, or cleanup.
    Recheck the event-loop clock before returning so work that finishes after the
    deadline is never reported as timely success. This is not a hard real-time
    execution bound; blocking work needs its own resource/isolation policy.

    `request_id` is assumed to be an internal correlation identifier rather than
    user-provided content. If that is not true in the host application, sanitize
    or replace it before logging.

    `user_id` appears in the request path. It must be non-sensitive and opaque when
    HTTP client, proxy, or server access logs can record paths; this module controls
    only its own logger.

    Preconditions on the injected `client`:

    - Its base URL must exactly match the fixed HTTPS origin in `config`. The
      host application remains responsible for TLS verification and trusted
      proxy/resolver configuration because HTTPX does not expose those policies
      for reliable introspection after client construction.
    - It must not follow redirects. This function classifies 3xx explicitly; a
      redirect-following client would instead chase up to `max_redirects` hops
      off-host with no validation, and the 3xx branch would become dead code.
    - It must not configure request or response event hooks. Such hooks can mutate
      the validated URL or headers, pre-decode the body, or strip response metadata
      before this function enforces its boundaries.
    - It must not perform transport-level retries. This function owns the retry
      loop, so a client built with `AsyncHTTPTransport(retries=N)` would
      multiply attempts by up to N + 1 - the nested-retry amplification the checklist
      warns about.
    """

    if client.follow_redirects:
        raise ValueError(
            "client must be constructed with follow_redirects=False; "
            "this function classifies 3xx responses itself"
        )
    if any(client.event_hooks.values()):
        raise ValueError("client must not configure request or response event hooks")
    if client.base_url != httpx.URL(config.expected_origin):
        raise ValueError("client base_url must match config.expected_origin exactly")

    _validate_user_id(user_id)
    _validate_request_id(request_id)

    async def run() -> FetchResult[UserProfile]:
        anon_id = pseudonymize(user_id, config.telemetry_key)

        for attempt in range(1, config.max_attempts + 1):
            permit = await breaker.allow()
            if permit is None:
                logger.warning(
                    "Circuit breaker rejected outbound user fetch",
                    extra={"request_id": request_id, "subject": anon_id},
                )
                return FetchResult(
                    status=FetchStatus.TEMPORARILY_UNAVAILABLE,
                    error_code="CIRCUIT_OPEN",
                )

            probe_resolved = False
            retry_error_code: str | None = None
            retry_after_hint: float | None = None

            try:
                async with client.stream(
                    "GET",
                    f"/users/{user_id}",
                    headers={"Accept-Encoding": "identity"},
                    timeout=config.attempt_timeout(),
                ) as resp:
                    status = resp.status_code

                    # This hypothetical dependency contract marks only these
                    # statuses transient. Do not generalize the allowlist: even an
                    # idempotent method should retry only failures expected to
                    # change inside the remaining deadline.
                    if status in RETRYABLE_HTTP_STATUSES:
                        await breaker.record_failure(permit)
                        probe_resolved = True
                        retry_error_code = "UPSTREAM_TRANSIENT_5XX"
                        hint = _parse_retry_after(
                            resp.headers.get("retry-after"), config.max_retry_after_s
                        )
                        if hint.exceeds_limit:
                            return FetchResult(
                                status=FetchStatus.TEMPORARILY_UNAVAILABLE,
                                error_code="RETRY_AFTER_EXCEEDS_BUDGET",
                            )
                        retry_after_hint = hint.delay_s

                    elif 500 <= status < 600:
                        await breaker.record_reachable(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UPSTREAM_PERMANENT_5XX",
                        )

                    elif status == 200:
                        # The hypothetical API contract expects a JSON profile only on 200.
                        content_encoding = resp.headers.get("content-encoding")
                        if (
                            content_encoding is not None
                            and content_encoding.strip().lower() != "identity"
                        ):
                            await breaker.record_reachable(permit)
                            probe_resolved = True
                            return FetchResult(
                                status=FetchStatus.INVALID_PAYLOAD,
                                error_code="UNSUPPORTED_CONTENT_ENCODING",
                            )
                        body = await _read_bounded_body(resp, config.max_response_bytes)
                        if body is None:
                            await breaker.record_success(permit)
                            probe_resolved = True
                            return FetchResult(
                                status=FetchStatus.INVALID_PAYLOAD,
                                error_code="RESPONSE_TOO_LARGE",
                            )

                        result = _parse_profile(body, user_id)
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return result

                    elif 201 <= status < 300:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_2XX_STATUS",
                        )

                    elif 300 <= status < 400:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_REDIRECT",
                        )

                    elif status == 401:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNAUTHENTICATED,
                            error_code="UNAUTHENTICATED",
                        )

                    elif status == 403:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.FORBIDDEN, error_code="FORBIDDEN"
                        )

                    elif status == 404:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(status=FetchStatus.NOT_FOUND)

                    elif status == 429:
                        # Contract assumption: 429 enforces a caller quota (`policy_limit`),
                        # not dependency saturation. Change this classification if the real
                        # upstream contract uses 429 to signal `overloaded` instead.
                        # HTTP status alone cannot distinguish policy limits from saturation.
                        await breaker.record_success(permit)
                        probe_resolved = True
                        hint = _parse_retry_after(
                            resp.headers.get("retry-after"), config.max_retry_after_s
                        )
                        return FetchResult(
                            status=FetchStatus.RATE_LIMITED,
                            error_code=(
                                "RETRY_AFTER_EXCEEDS_BUDGET"
                                if hint.exceeds_limit
                                else "RATE_LIMITED"
                            ),
                            retry_after_s=hint.delay_s,
                        )

                    elif status == 408:
                        # This GET is contractually idempotent, so RFC 9110 s9.2.2
                        # permits automatic replay after a communication failure.
                        # The same response does not prove a write was unapplied.
                        # Breaker-neutral: 408 describes request transmission, not
                        # dependency availability.
                        await breaker.record_reachable(permit)
                        probe_resolved = True
                        retry_error_code = "UPSTREAM_REQUEST_TIMEOUT"
                        hint = _parse_retry_after(
                            resp.headers.get("retry-after"), config.max_retry_after_s
                        )
                        if hint.exceeds_limit:
                            return FetchResult(
                                status=FetchStatus.TEMPORARILY_UNAVAILABLE,
                                error_code="RETRY_AFTER_EXCEEDS_BUDGET",
                            )
                        retry_after_hint = hint.delay_s

                    elif status == 400:
                        await breaker.record_success(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.INVALID_REQUEST,
                            error_code="CLIENT_ERROR",
                        )

                    elif 400 <= status < 500:
                        await breaker.record_reachable(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_CLIENT_STATUS",
                        )

                    else:
                        await breaker.record_reachable(permit)
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_HTTP_STATUS",
                        )

            except httpx.DecodingError:
                await breaker.record_reachable(permit)
                probe_resolved = True
                return FetchResult(
                    status=FetchStatus.INVALID_PAYLOAD,
                    error_code="UNSUPPORTED_CONTENT_ENCODING",
                )
            except httpx.PoolTimeout:
                return FetchResult(
                    status=FetchStatus.OVERLOADED,
                    error_code="LOCAL_POOL_TIMEOUT",
                )
            except (TimeoutError, httpx.TimeoutException):
                await breaker.record_failure(permit)
                probe_resolved = True
                retry_error_code = "UPSTREAM_TIMEOUT"
            except httpx.NetworkError:
                await breaker.record_failure(permit)
                probe_resolved = True
                retry_error_code = "TRANSPORT_ERROR"
            except httpx.RequestError:
                return FetchResult(
                    status=FetchStatus.UNEXPECTED_RESPONSE,
                    error_code="NON_RETRYABLE_REQUEST_ERROR",
                )
            finally:
                if not probe_resolved:
                    await breaker.release_probe(permit)

            if retry_error_code is None:
                # Defensive invariant: all retry paths must state why they are retrying.
                return FetchResult(
                    status=FetchStatus.INTERNAL_ERROR,
                    error_code="INTERNAL_RETRY_STATE_ERROR",
                )

            if attempt == config.max_attempts:
                logger.error(
                    "User fetch retries exhausted",
                    extra={
                        "request_id": request_id,
                        "subject": anon_id,
                        "attempts": config.max_attempts,
                        "error_code": retry_error_code,
                    },
                )
                return FetchResult(
                    status=FetchStatus.TEMPORARILY_UNAVAILABLE,
                    error_code=retry_error_code,
                    retry_after_s=retry_after_hint,
                )

            raw_delay = min(
                config.max_delay_s, config.base_delay_s * (2 ** (attempt - 1))
            )
            jitter = random.uniform(0.0, raw_delay)
            # Retry-After is a minimum, not an exact synchronized wake time.
            # Positive jitter spreads clients; the outer deadline caps total wait.
            await asyncio.sleep((retry_after_hint or 0.0) + jitter)

        # Unreachable: every path above returns. Reaching here is an internal
        # invariant break, not a dependency problem.
        return FetchResult(
            status=FetchStatus.INTERNAL_ERROR,
            error_code="UNKNOWN_FAILURE",
        )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + config.deadline_s
    try:
        async with asyncio.timeout_at(deadline):
            result = await run()
            # Synchronous work or an uncontended await can cross the deadline
            # without yielding to the timeout callback. Check before returning.
            if loop.time() >= deadline:
                raise TimeoutError
            return result
    except TimeoutError:
        logger.warning(
            "User fetch exceeded operation deadline", extra={"request_id": request_id}
        )
        return FetchResult(
            status=FetchStatus.CANCELLED,
            error_code="DEADLINE_EXCEEDED",
        )
