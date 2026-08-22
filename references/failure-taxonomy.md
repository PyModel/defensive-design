# Failure Taxonomy

Companion to `SKILL.md`. Use when a failure is hard to classify, when several
outcomes are collapsing into one return value, or when designing an error
contract that crosses a service boundary.

Classify before handling. The class determines retryability, caller treatment,
and whether an effect may already exist.

| Class | Meaning | Retry | Caller treatment |
|---|---|---|---|
| `absence` | Validly no matching object or data | No | Explicit no-data result, not an error |
| `invalid` | Malformed, unsupported, or semantically invalid input | No | Stable validation failure |
| `unauthenticated` | Identity cannot be established | No | Deny; fail closed |
| `unauthorized` | Established principal lacks permission | No | Deny without revealing protected detail |
| `conflict` | State, version, or concurrency precondition failed | Conditional | Conflict; retry only if operation semantics allow it |
| `overloaded` | Capacity, quota, concurrency, memory, token, or spend budget exhausted | Usually not immediately | Shed or throttle; give retry guidance when meaningful |
| `transient_dependency` | Temporary remote or network failure, **outcome known** | Bounded | Retry inside the remaining deadline and budget |
| `permanent_dependency` | Auth, config, protocol, schema, or not-found condition unlikely to change during this attempt | No | Fail fast; surface the actionable dependency class |
| `unknown_outcome` | A write may or may not have committed | Never blind | Reconcile, or replay under the same idempotency identity |
| `partial_success` | Some intended effects completed, others did not | Per policy | Explicit per-item status plus a recovery path |
| `stale_work` | Deadline, TTL, lease, or version has passed; the work is no longer useful | No | Drop or cancel rather than consume capacity |
| `cancelled` | Caller or system deliberately abandoned the operation | No | Propagate cancellation, release resources |
| `invariant_violation` | Impossible, corrupt, or security-sensitive state observed | No | Stop the unsafe path; quarantine or escalate |

## `transient_dependency` versus `unknown_outcome`

This is the distinction that most often goes wrong.

A read that times out is `transient_dependency`: the caller learned nothing
happened that matters, so a retry is safe. A side-effecting write that times
out is `unknown_outcome`: the server may have committed the effect and only the
response was lost. Absence of a response is not evidence of non-commit.

The correct responses to `unknown_outcome` are: query the provider for the
operation's status, replay under the *same* idempotency identity so the second
attempt resolves to the first effect, or hand the operation to reconciliation.
A blind repeat is a duplicate charge, a duplicate email, or a duplicate row.

## Failure envelope

Carry the semantics, not necessarily this literal shape. Any representation
that answers these questions is sufficient; a class hierarchy is not required.

```text
failure_class      one of the classes above
retryable          under this dependency's contract, not in general
outcome            not_started | committed | not_committed | unknown | partial
scope              request | dependency | partition | service
safe_to_degrade    whether a fallback preserves every higher-order invariant
retry_after        server hint, bounded before use
operation_id       idempotency or correlation identity
cause              internal detail, preserved but not exposed verbatim
```

For each class that a design actually reaches, answer:

- Can a retry change the answer?
- Is the previous outcome known?
- Can repeating the operation duplicate an effect?
- Can degradation preserve every critical invariant?
- Does retry or recovery add pressure to the failing dependency?
- What should the caller observe?
- What evidence proves the behavior?

## Expressing the classes across a boundary

Do not use `None`, `false`, an empty collection, or a generic 500 to carry more
than one of these classes unless the contract distinguishes them elsewhere.

Over HTTP, RFC 9457 problem details give a machine-readable representation: a
stable `type` URI per failure class, a `title`, and extension members for
retryability, outcome certainty, and correlation identity. That is preferable to
overloading status codes alone, since 409, 422, and 503 each cover several
classes above.

Whatever the transport, the failure class must survive it. A gateway that
rewrites `unauthorized` into a generic 500, or `unknown_outcome` into a plain
timeout, destroys the information the caller needs to act safely.
