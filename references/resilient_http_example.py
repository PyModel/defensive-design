"""Illustrative defensive outbound HTTP GET pattern.

This example intentionally demonstrates only mechanisms that are relevant to a
read-only HTTP lookup: strict configuration/input validation, a hard operation
deadline, bounded/capped retry with full jitter, a small async circuit breaker,
bounded response streaming, typed outcomes, URL path encoding, and redacted
identifier logging.

It deliberately does not invent a metrics/tracing stack. Production callers
should integrate with their existing telemetry system.
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
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True, kw_only=True)
class ResilienceConfig:
    """Validated operational policy for the example client."""

    telemetry_key: bytes
    deadline_s: float = 5.0
    per_attempt_timeout_s: float = 2.0
    max_attempts: int = 3
    base_delay_s: float = 0.2
    max_delay_s: float = 2.0
    max_response_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        for name, value in (
            ("deadline_s", self.deadline_s),
            ("per_attempt_timeout_s", self.per_attempt_timeout_s),
            ("base_delay_s", self.base_delay_s),
            ("max_delay_s", self.max_delay_s),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite, positive number")

        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise ValueError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        if isinstance(self.max_response_bytes, bool) or not isinstance(self.max_response_bytes, int):
            raise ValueError("max_response_bytes must be an integer")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1")

        if self.base_delay_s > self.max_delay_s:
            raise ValueError("base_delay_s cannot exceed max_delay_s")

        if not isinstance(self.telemetry_key, bytes) or len(self.telemetry_key) < 16:
            raise ValueError("telemetry_key must be at least 16 bytes")


class FetchStatus(Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    INVALID_PAYLOAD = "invalid_payload"
    UNEXPECTED_RESPONSE = "unexpected_response"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    display_name: str
    email_domain: str


@dataclass(frozen=True)
class FetchResult(Generic[T]):
    status: FetchStatus
    data: T | None = None
    error_code: str | None = None


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AsyncCircuitBreaker:
    """Single-event-loop task-safe breaker with one HALF_OPEN probe at a time.

    This is intentionally small and illustrative. Prefer a proven platform or
    client-library breaker when one already exists and satisfies the contract.
    """

    def __init__(self, *, failure_threshold: int = 5, reset_timeout_s: float = 30.0) -> None:
        if isinstance(failure_threshold, bool) or not isinstance(failure_threshold, int):
            raise ValueError("failure_threshold must be an integer")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if (
            isinstance(reset_timeout_s, bool)
            or not isinstance(reset_timeout_s, (int, float))
            or not math.isfinite(reset_timeout_s)
            or reset_timeout_s <= 0
        ):
            raise ValueError("reset_timeout_s must be a finite, positive number")

        self.failure_threshold = failure_threshold
        self.reset_timeout_s = float(reset_timeout_s)
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._probing = False
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

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            if self._state is CircuitState.OPEN:
                if now - self._opened_at < self.reset_timeout_s:
                    return False
                self._state = CircuitState.HALF_OPEN
                self._probing = True
                return True

            if self._state is CircuitState.HALF_OPEN:
                if self._probing:
                    return False
                self._probing = True
                return True

            return True

    async def record_success(self) -> None:
        """Dependency answered with a contract-defined healthy/reachable outcome."""
        async with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED
            self._probing = False

    async def record_failure(self) -> None:
        """Dependency had a transport/timeout/5xx availability failure."""
        async with self._lock:
            was_half_open = self._state is CircuitState.HALF_OPEN
            self._failures += 1
            self._probing = False
            if self._failures >= self.failure_threshold or was_half_open:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    async def release_probe(self) -> None:
        """Release an unresolved HALF_OPEN probe after cancellation/unexpected exit."""
        async with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._probing = False


def pseudonymize(identifier: str, key: bytes) -> str:
    return hmac.new(key, identifier.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _validate_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not (1 <= len(user_id) <= 128):
        raise ValueError("user_id must be a string between 1 and 128 characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in user_id):
        raise ValueError("user_id must not contain ASCII control characters")


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

    body = bytearray()
    async for chunk in resp.aiter_bytes():
        if len(body) + len(chunk) > max_bytes:
            return None
        body.extend(chunk)
    return bytes(body)


def _parse_profile(body: bytes, user_id: str) -> FetchResult[UserProfile]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return FetchResult(status=FetchStatus.INVALID_PAYLOAD, error_code="MALFORMED_JSON")

    if not isinstance(payload, dict):
        return FetchResult(status=FetchStatus.INVALID_PAYLOAD, error_code="SCHEMA_VIOLATION")

    display_name = payload.get("display_name")
    email_domain = payload.get("email_domain", "unknown")

    if not isinstance(display_name, str) or not (1 <= len(display_name) <= 100):
        return FetchResult(status=FetchStatus.INVALID_PAYLOAD, error_code="INVALID_DISPLAY_NAME")
    if not isinstance(email_domain, str) or not (1 <= len(email_domain) <= 100):
        return FetchResult(status=FetchStatus.INVALID_PAYLOAD, error_code="INVALID_EMAIL_DOMAIN")

    return FetchResult(
        status=FetchStatus.SUCCESS,
        data=UserProfile(user_id=user_id, display_name=display_name, email_domain=email_domain),
    )


async def fetch_user_profile(
    client: httpx.AsyncClient,
    breaker: AsyncCircuitBreaker,
    *,
    user_id: str,
    request_id: str,
    config: ResilienceConfig,
) -> FetchResult[UserProfile]:
    """Fetch a user profile under one hard wall-clock deadline.

    `request_id` is assumed to be an internal correlation identifier rather than
    user-provided content. If that is not true in the host application, sanitize
    or replace it before logging.
    """

    _validate_user_id(user_id)
    if not isinstance(request_id, str) or not (1 <= len(request_id) <= 128):
        raise ValueError("request_id must be a string between 1 and 128 characters")

    async def run() -> FetchResult[UserProfile]:
        safe_user_id = quote(user_id, safe="")
        anon_id = pseudonymize(user_id, config.telemetry_key)

        for attempt in range(1, config.max_attempts + 1):
            if not await breaker.allow():
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

            try:
                async with client.stream(
                    "GET",
                    f"/users/{safe_user_id}",
                    timeout=config.per_attempt_timeout_s,
                ) as resp:
                    status = resp.status_code

                    # Availability failures are classified before any payload logic.
                    if 500 <= status < 600:
                        await breaker.record_failure()
                        probe_resolved = True
                        retry_error_code = "UPSTREAM_5XX"

                    elif status == 200:
                        # The hypothetical API contract expects a JSON profile only on 200.
                        body = await _read_bounded_body(resp, config.max_response_bytes)
                        if body is None:
                            await breaker.record_success()
                            probe_resolved = True
                            return FetchResult(
                                status=FetchStatus.INVALID_PAYLOAD,
                                error_code="RESPONSE_TOO_LARGE",
                            )

                        result = _parse_profile(body, user_id)
                        await breaker.record_success()
                        probe_resolved = True
                        return result

                    elif 201 <= status < 300:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_2XX_STATUS",
                        )

                    elif 300 <= status < 400:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_REDIRECT",
                        )

                    elif status == 401:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNAUTHENTICATED,
                            error_code="UNAUTHENTICATED",
                        )

                    elif status == 403:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(status=FetchStatus.FORBIDDEN, error_code="FORBIDDEN")

                    elif status == 404:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(status=FetchStatus.NOT_FOUND)

                    elif status == 429:
                        # Contract assumption for this example: 429 is caller/quota throttling,
                        # not evidence that the dependency is unavailable. Change this policy if
                        # the real upstream uses 429 to signal service overload.
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.RATE_LIMITED,
                            error_code="RATE_LIMITED",
                        )

                    elif 400 <= status < 500:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.INVALID_REQUEST,
                            error_code="CLIENT_ERROR",
                        )

                    else:
                        await breaker.record_success()
                        probe_resolved = True
                        return FetchResult(
                            status=FetchStatus.UNEXPECTED_RESPONSE,
                            error_code="UNEXPECTED_HTTP_STATUS",
                        )

            except (TimeoutError, httpx.TimeoutException):
                await breaker.record_failure()
                probe_resolved = True
                retry_error_code = "UPSTREAM_TIMEOUT"
            except httpx.RequestError:
                await breaker.record_failure()
                probe_resolved = True
                retry_error_code = "TRANSPORT_ERROR"
            finally:
                if not probe_resolved:
                    await breaker.release_probe()

            if retry_error_code is None:
                # Defensive invariant: all retry paths must state why they are retrying.
                return FetchResult(
                    status=FetchStatus.TEMPORARILY_UNAVAILABLE,
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
                )

            raw_delay = min(config.max_delay_s, config.base_delay_s * (2 ** (attempt - 1)))
            await asyncio.sleep(random.uniform(0.0, raw_delay))

        return FetchResult(
            status=FetchStatus.TEMPORARILY_UNAVAILABLE,
            error_code="UNKNOWN_FAILURE",
        )

    try:
        async with asyncio.timeout(config.deadline_s):
            return await run()
    except TimeoutError:
        logger.warning("User fetch exceeded operation deadline", extra={"request_id": request_id})
        return FetchResult(
            status=FetchStatus.TEMPORARILY_UNAVAILABLE,
            error_code="DEADLINE_EXCEEDED",
        )
