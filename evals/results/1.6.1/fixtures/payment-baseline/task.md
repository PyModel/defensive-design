# Repair payment submission and recovery

Implement the repair in `payment.py`. Preserve `Store`, `PaymentResult`, `submit` and
`reconcile` signatures. This fixture is an in-memory single-process application with
concurrent worker threads; a shared `Store` represents its already accepted operation
records across worker restarts. Do not introduce infrastructure or dependencies.

`tenant_id` is the authenticated tenant context. `operation_id` is a globally unique
business-operation identifier; both are ASCII letters/digits/underscore/hyphen, 1–64
characters. `amount_cents` must be an integer (not a boolean), 1–100,000,000. Reject
invalid input with `ValueError` before provider effects. Reusing an operation with a
different tenant or amount is also `ValueError`, without revealing its receipt.

The provider has `charge(key: str, amount_cents: int) -> str` and
`lookup(key: str) -> str | None`. Calls have an SDK-managed timeout. A charge timeout or
connection error may happen after the provider committed. A lookup returning `None`
is inconclusive, not proof that the charge failed. A returned receipt is authoritative.
The provider deduplicates an identity only within its retention window; do not use a
fresh identity or blindly submit again when an earlier effect is pending or unknown.

Return `PaymentResult("completed", receipt)` only after a receipt is stored; otherwise
return `PaymentResult("pending", None)` for an accepted uncertain/in-flight operation.
Concurrent duplicates must never create an extra charge. A slow provider call for one
operation must not hold a global store lock that blocks unrelated operations. Calling
`reconcile` may read provider status to finish a pending operation; an inconclusive or
transiently failing lookup leaves it pending and must not charge again. Preserve
operation identity and ownership across uncertainty. Unexpected provider exceptions
must propagate, with the operation still safe to reconcile rather than retry blindly.

No credentials, network or production services are available. Explain your changes
and report only verification you actually execute.
