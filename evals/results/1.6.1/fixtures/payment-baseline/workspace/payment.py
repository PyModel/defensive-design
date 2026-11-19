"""Thread-safe payment submission with conservative recovery of uncertain effects."""
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
    def __init__(self) -> None:
        self.results: dict[str, PaymentResult] = {}
        self._operations: dict[str, _Operation] = {}
        self.lock = Lock()


def _validate(operation_id: str, tenant_id: str, amount_cents: int) -> None:
    for name, value in (("operation_id", operation_id), ("tenant_id", tenant_id)):
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"{name} must contain 1-64 ASCII letters, digits, '_' or '-'")
    if (isinstance(amount_cents, bool) or not isinstance(amount_cents, int)
            or not 1 <= amount_cents <= 100_000_000):
        raise ValueError("amount_cents must be an integer from 1 to 100000000")


def _check_ownership(operation: _Operation, tenant_id: str, amount_cents: int) -> None:
    if operation.tenant_id != tenant_id or operation.amount_cents != amount_cents:
        raise ValueError("operation_id is already associated with different payment details")


def _current_result(store: Store, operation_id: str) -> PaymentResult:
    with store.lock:
        return store.results[operation_id]


def _complete(store: Store, operation_id: str, receipt: str) -> PaymentResult:
    # A malformed provider response must not turn uncertainty into completion.
    if not isinstance(receipt, str):
        raise TypeError("provider receipt must be a string")
    with store.lock:
        result = store.results[operation_id]
        if result.status != "completed":
            result = PaymentResult("completed", receipt)
            store.results[operation_id] = result
        return result


def submit(store: Store, provider: Provider, operation_id: str,
           tenant_id: str, amount_cents: int) -> PaymentResult:
    _validate(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is not None:
            _check_ownership(operation, tenant_id, amount_cents)
            return store.results[operation_id]

        # Reserve ownership and identity before any provider effect. Only this
        # invocation may charge; even an unexpected exception leaves the claim.
        operation = _Operation(tenant_id, amount_cents, operation_id)
        store._operations[operation_id] = operation
        store.results[operation_id] = _PENDING

    # Never hold the shared store lock across provider I/O.
    try:
        receipt = provider.charge(operation.provider_key, amount_cents)
    except (TimeoutError, ConnectionError):
        # A concurrent reconciliation may already have saved the receipt.
        return _current_result(store, operation_id)
    return _complete(store, operation_id, receipt)


def reconcile(store: Store, provider: Provider, operation_id: str,
              tenant_id: str, amount_cents: int) -> PaymentResult:
    _validate(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is None:
            raise ValueError("operation_id has not been submitted")
        _check_ownership(operation, tenant_id, amount_cents)
        result = store.results[operation_id]
        if result.status == "completed":
            return result

    try:
        receipt = provider.lookup(operation.provider_key)
    except (TimeoutError, ConnectionError):
        return _current_result(store, operation_id)
    if receipt is None:
        # Absence is inconclusive, including after provider deduplication expires.
        return _current_result(store, operation_id)
    return _complete(store, operation_id, receipt)
