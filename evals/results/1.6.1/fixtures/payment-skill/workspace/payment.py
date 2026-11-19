"""Single-process payment submission with lookup-only uncertain-effect recovery."""
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


class Store:
    def __init__(self) -> None:
        self.results: dict[str, PaymentResult] = {}
        self._operations: dict[str, _Operation] = {}
        self.lock = Lock()


_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _validate(operation_id: str, tenant_id: str, amount_cents: int) -> None:
    for name, value in (("operation_id", operation_id), ("tenant_id", tenant_id)):
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"{name} must contain 1-64 ASCII letters, digits, '_' or '-'")
    if (not isinstance(amount_cents, int) or isinstance(amount_cents, bool)
            or not 1 <= amount_cents <= 100_000_000):
        raise ValueError("amount_cents must be an integer from 1 to 100000000")


def _check_owner(operation: _Operation, tenant_id: str, amount_cents: int) -> None:
    if operation.tenant_id != tenant_id or operation.amount_cents != amount_cents:
        # Never include the stored tenant, amount or receipt in a conflict error.
        raise ValueError("operation does not match tenant and amount")


def _record_receipt(store: Store, operation_id: str,
                    receipt: str | None) -> PaymentResult:
    if receipt is not None and not isinstance(receipt, str):
        raise TypeError("provider returned a non-string receipt")
    with store.lock:
        result = store.results[operation_id]
        # A slow lookup or charge failure must not undo another worker's completion.
        if receipt is not None and result.status != "completed":
            result = PaymentResult("completed", receipt)
            store.results[operation_id] = result
        return result


def submit(store: Store, provider: Provider, operation_id: str,
           tenant_id: str, amount_cents: int) -> PaymentResult:
    _validate(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is not None:
            _check_owner(operation, tenant_id, amount_cents)
            return store.results[operation_id]

        # The business operation ID is globally unique. Claim its identity and
        # ownership before any provider effect, and retain them for this Store's
        # lifetime, including timeouts and unexpected exceptions.
        operation = _Operation(tenant_id, amount_cents, operation_id)
        store._operations[operation_id] = operation
        store.results[operation_id] = PaymentResult("pending", None)

    # Only the worker that created the accepted record may call charge. No I/O
    # holds the store lock; duplicates return the already accepted state.
    try:
        receipt = provider.charge(operation.provider_key, operation.amount_cents)
    except (TimeoutError, ConnectionError):
        return _record_receipt(store, operation_id, None)
    if receipt is None:
        raise TypeError("provider charge returned no receipt")
    return _record_receipt(store, operation_id, receipt)


def reconcile(store: Store, provider: Provider, operation_id: str,
              tenant_id: str, amount_cents: int) -> PaymentResult:
    """Read status for an accepted operation; an unknown operation is invalid."""
    _validate(operation_id, tenant_id, amount_cents)
    with store.lock:
        operation = store._operations.get(operation_id)
        if operation is None:
            raise ValueError("operation does not match tenant and amount")
        _check_owner(operation, tenant_id, amount_cents)
        result = store.results[operation_id]
        if result.status == "completed":
            return result

    try:
        receipt = provider.lookup(operation.provider_key)
    except (TimeoutError, ConnectionError):
        receipt = None
    # None is inconclusive, even after the provider's deduplication retention
    # expires. Never resubmit or replace the accepted operation's identity.
    return _record_receipt(store, operation_id, receipt)
