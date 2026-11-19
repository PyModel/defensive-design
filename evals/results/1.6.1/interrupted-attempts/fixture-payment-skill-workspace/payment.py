"""Single-process payments with retained ownership and lookup-only recovery."""
from __future__ import annotations

from dataclasses import dataclass
import re
from threading import Lock
from typing import Protocol


class Provider(Protocol):
    def charge(self, key: str, amount_cents: int) -> str: ...
    def lookup(self, key: str) -> str | None: ...


@dataclass(frozen=True)
class PaymentResult:
    status: str
    receipt: str | None


@dataclass(frozen=True)
class _Operation:
    tenant_id: str
    amount_cents: int
    provider_key: str


_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}")
_PENDING = PaymentResult("pending", None)


class Store:
    """Retain this shared store across worker restarts; do not expire operations.

    The module owns mutations of both maps. The lock protects only local state,
    never a provider call. ``results`` remains available for result inspection.
    """

    def __init__(self) -> None:
        self.results: dict[str, PaymentResult] = {}
        self._operations: dict[str, _Operation] = {}
        self.lock = Lock()


def _validate_request(operation_id: str, tenant_id: str, amount_cents: int) -> None:
    for name, value in (("operation_id", operation_id), ("tenant_id", tenant_id)):
        if (not isinstance(value, str) or not 1 <= len(value) <= 64
                or _IDENTIFIER.fullmatch(value) is None):
            raise ValueError(f"{name} must be 1-64 ASCII letters, digits, '_' or '-'")
    if (not isinstance(amount_cents, int) or isinstance(amount_cents, bool)
            or not 1 <= amount_cents <= 100_000_000):
        raise ValueError("amount_cents must be an integer between 1 and 100000000")


def _check_request(operation: _Operation, tenant_id: str, amount_cents: int) -> None:
    if operation.tenant_id != tenant_id or operation.amount_cents != amount_cents:
        # Never include the original tenant, amount or receipt in this error.
        raise ValueError("operation_id is already bound to a different request")


def _current_result(store: Store, operation_id: str) -> PaymentResult:
    with store.lock:
        return store.results[operation_id]


def _complete(store: Store, operation_id: str, receipt: str) -> PaymentResult:
    if not isinstance(receipt, str):
        raise TypeError("provider returned an invalid receipt")
    with store.lock:
        # A concurrent lookup may already have stored authoritative completion.
        # Neither a late response nor an inconclusive lookup may undo that fact.
        result = store.results[operation_id]
        if result.status != "completed":
            result = PaymentResult("completed", receipt)
            store.results[operation_id] = result
        return result


def submit(store: Store, provider: Provider, operation_id: str,
           tenant_id: str, amount_cents: int) -> PaymentResult:
    """Claim a new operation before its only charge attempt, or return its state."""
    _validate_request(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is not None:
            _check_request(operation, tenant_id, amount_cents)
            return store.results[operation_id]
        # Business-operation IDs are globally unique. Persist the identity and
        # request binding before crossing the provider's effect boundary.
        operation = _Operation(tenant_id, amount_cents, operation_id)
        store._operations[operation_id] = operation
        store.results[operation_id] = _PENDING

    try:
        receipt = provider.charge(operation.provider_key, operation.amount_cents)
    except (TimeoutError, ConnectionError):
        return _current_result(store, operation_id)
    # Other exceptions propagate with the accepted operation still retained.
    return _complete(store, operation_id, receipt)


def reconcile(store: Store, provider: Provider, operation_id: str,
              tenant_id: str, amount_cents: int) -> PaymentResult:
    """Look up an accepted operation; unknown IDs are rejected without effects."""
    _validate_request(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is None:
            raise ValueError("operation_id has not been submitted")
        _check_request(operation, tenant_id, amount_cents)
        result = store.results[operation_id]
        if result.status == "completed":
            return result

    try:
        receipt = provider.lookup(operation.provider_key)
    except (TimeoutError, ConnectionError):
        return _current_result(store, operation_id)
    if receipt is None:
        # Absence is inconclusive even after provider deduplication has expired.
        return _current_result(store, operation_id)
    return _complete(store, operation_id, receipt)
