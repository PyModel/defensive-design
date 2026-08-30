# Failure Taxonomy

Use this reference when a failure is hard to classify, several outcomes collapse
into one return value, or a contract crosses a process or service boundary.

## Use Several Axes, Not One Error Enum

A single event can be overloaded, partially committed, and unsafe to retry. Record
the dimensions that change a decision; do not force compatible facts into one
`failure_class` field.

| Axis | Question | Stable labels |
|---|---|---|
| Result | What should the caller observe? | `success`, `absence`, `invalid`, `unauthenticated`, `unauthorized`, `conflict`, `degraded`, `cancelled`, `failed` |
| Cause | Why did it happen? | `transient_dependency`, `permanent_dependency`, `invariant_violation`, or a repository-native domain cause |
| Effect certainty | Did the intended effect occur? | `not_started`, `not_committed`, `committed`, `unknown_outcome`, `partial_success` |
| Policy | Did an authoritative limit decide it? | `policy_limit` or a repository-native policy result |
| State | Which operating condition changes handling? | `overloaded`, `stale_work`, or a repository-native state |
| Scope | How much is affected? | request, key, tenant, partition, dependency, service |
| Retry policy | May this caller repeat it now? | never, conditional, bounded; include owner, attempt budget, and deadline |

Use only labels the operation can actually reach. Carry the semantics in existing
repository types when they already express them; this table does not require a new
class hierarchy.

## Default Decisions

| Label | Meaning | Default handling |
|---|---|---|
| `success` | Intended result completed and is available | Return the contract-defined result |
| `absence` | Validly no matching object or data | Explicit no-data result; no retry |
| `invalid` | Malformed, unsupported, or semantically invalid input or output | Stable rejection; no retry |
| `unauthenticated` | Identity cannot be established | Deny without revealing protected detail |
| `unauthorized` | Principal lacks authority | Deny; never widen authority through fallback |
| `conflict` | State, version, or concurrency precondition failed | Return conflict; compare-and-retry only when designed |
| `policy_limit` | Security, abuse, cost, safety, or contractual limit reached | Enforce the authoritative limit; fail closed if enforcement is unavailable |
| `overloaded` | Capacity, concurrency, memory, or queue saturation | Backpressure, reject, defer, or shed; do not hot-retry |
| `transient_dependency` | Contract-defined dependency failure likely to change during this operation | Bounded retry only when repeat-safe and budget remains |
| `permanent_dependency` | Configuration, protocol, authentication, schema, or other failure unlikely to change during this operation | Fail fast; no retry |
| `unknown_outcome` | An effect may or may not have committed | Status lookup, same-identity replay, or reconciliation; never blind repeat |
| `partial_success` | Some intended effects committed | Explicit per-item/effect state plus compensation or reconciliation |
| `stale_work` | Deadline, TTL, lease, or version passed; work is no longer useful | Drop or cancel rather than consume capacity |
| `degraded` | A bounded fallback returned lower-fidelity service | Label it, preserve critical invariants, observe it, and recover |
| `cancelled` | Caller or system abandoned the operation | Propagate cancellation and release owned resources |
| `failed` | Operation ended without a more specific caller result | Return stable failure; preserve the cause; do not infer retryability |
| `invariant_violation` | Impossible, corrupt, or security-sensitive state observed | Stop the unsafe path; preserve evidence; quarantine or escalate |

`not_found` is not automatically permanent: valid absence, a lagging replica, and a
misconfigured endpoint have different causes and retry policies. Classify against the
real dependency contract.

## Repeat Safety

For an automatic transport retry, all applicable answers must be yes:

1. Is the failure contract-defined as transient?
2. Is this layer the single retry owner?
3. Does the overall deadline and attempt budget still allow useful work?
4. Will repetition preserve the intended effect, or is it protected by the same
   idempotency identity and atomic deduplication?
5. If the prior effect is uncertain, can status lookup, same-key replay, or
   reconciliation resolve it without duplication?
6. Will retrying avoid amplifying overload?

Conflict compare-and-retry and same-identity replay or reconciliation after an unknown
outcome are semantic recovery, not automatic transport retry. They still require one
owner, an attempt/deadline budget, and effect-once protection.

Operation names are not proof. A lookup may be repeat-safe, but a "read" that dequeues,
leases, bills, marks state, or advances a cursor is effectful. An HTTP method supplies
useful protocol semantics, but the resource contract, effect certainty, and any
idempotency protection still determine the safe action.

## Policy Limit Versus Overload

Keep these separate even when both surface as `429` or `RESOURCE_EXHAUSTED`:

- `policy_limit` preserves an invariant such as abuse prevention, spend, safety, or a
  contractual quota. Its backing-store failure must not silently grant more authority
  or budget.
- `overloaded` means the system lacks current capacity. Admission control, queue bounds,
  priority, and shedding protect recovery.

For a distributed policy limit, define the authoritative store, atomic increment or
reservation, reset semantics, key-cardinality bound, behavior during store failure, and
audit signal. Do not call a process-local counter globally enforced.

## Failure Envelope

Carry the semantics, not necessarily this literal shape:

```text
result             caller-visible result label
cause              dependency, domain, or invariant cause
effect             not_started | not_committed | committed | unknown_outcome | partial_success
policy             authoritative limit outcome, if any
state              overload, staleness, or other handling-relevant state
scope              request | key | tenant | partition | dependency | service
retry_policy       never | conditional | bounded, including the condition
retry_owner        the one layer allowed to retry
retry_after        bounded server or policy hint
attempt_budget     maximum and remaining attempts
deadline           absolute or remaining operation budget
idempotency_identity duplicate-effect identity, scoped and retained for replay
correlation_id     approved opaque diagnostic identity, never a substitute for idempotency
safe_to_degrade    whether every critical invariant survives fallback
cause_detail       internal evidence, preserved but not exposed verbatim
```

Before crossing a boundary, make sure the caller can distinguish every result it must
handle and can recover an uncertain or partial effect.

Keep idempotency and correlation identities separate. They differ in reuse, scope,
retention, secrecy, and telemetry policy; neither is automatically safe to expose.

## Expressing It Over HTTP

Do not overload `null`, `false`, an empty collection, or a generic 500 with several
meanings. RFC 9457 problem details can carry a stable `type` URI plus bounded extension
members for retry policy, effect certainty, correlation identity, and partial state.
Status codes alone are insufficient because one code can represent several causes.

A gateway must preserve the actionable distinction. Rewriting `unauthorized` as 500,
`policy_limit` as ordinary overload, or `unknown_outcome` as a plain timeout destroys
information the caller needs to act safely.
