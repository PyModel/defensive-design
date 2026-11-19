"""Small payment worker. Repair the defects described in the task."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from uuid import uuid4


class Provider(Protocol):
    def charge(self, key: str, amount_cents: int) -> str: ...
    def lookup(self, key: str) -> str | None: ...


@dataclass(frozen=True)
class PaymentResult:
    status: str
    receipt: str | None


class Store:
    def __init__(self) -> None:
        self.results: dict[str, PaymentResult] = {}
        self.lock = Lock()


def submit(store: Store, provider: Provider, operation_id: str,
           tenant_id: str, amount_cents: int) -> PaymentResult:
    with store.lock:
        if operation_id in store.results:
            return store.results[operation_id]
        try:
            receipt = provider.charge(str(uuid4()), amount_cents)
        except (TimeoutError, ConnectionError):
            return PaymentResult("pending", None)
        result = PaymentResult("completed", receipt)
        store.results[operation_id] = result
        return result


def reconcile(store: Store, provider: Provider, operation_id: str,
              tenant_id: str, amount_cents: int) -> PaymentResult:
    return submit(store, provider, operation_id, tenant_id, amount_cents)
