# Defensive Design Behavior Rubric

Use these expectations to grade behavior after trigger selection. Judge outcomes and engineering properties, not whether a specific mechanism appears by name.

| ID | Expected behavior |
|---|---|
| test-01 | Invokes the skill and identifies material HTTP failure surfaces without forcing irrelevant infrastructure. |
| test-02 | Classifies transient/permanent failures, preserves payment idempotency, uses existing retry ownership where available, redacts sensitive telemetry, and avoids duplicate resilience layers. |
| test-03 | Focuses on idempotency/deduplication, ambiguous-write/ack boundaries, transaction semantics, and retry ownership. |
| test-04 | Does not invoke the skill; returns a simple deterministic implementation. |
| test-05 | Does not invoke the skill; performs only the requested refactor. |
| test-06 | Does not invoke the skill; does not manufacture retry/circuit-breaker machinery for a throwaway fixture statement. |
| test-07 | Applies trust-boundary validation, size/type/schema constraints as applicable; omits retries/circuit breakers unless another dependency exists. |
| test-08 | Does not invoke the skill for a trusted hard-coded unit-test fixture. |
| test-09 | Returns the requested bug list/review format; does not force a three-step implementation or rewrite code. |
| test-10 | Examines cancellation propagation, cleanup, resource release, task ownership, and shutdown; labels claims `verified` / `reasoned_not_run` / `blocked` / `not_applicable` honestly. |
| test-11 | Fails authorization closed on dependency error; does not convert timeout/unavailability into allow. |
| test-12 | Propagates cancellation and cleans up only resources actually acquired (files, temp files, locks, sockets, child tasks); does not invent circuit-breaker probes. |
| test-13 | Detects existing SDK retry ownership and avoids adding a second retry loop; may improve deadlines, error classification, idempotency, or observability if relevant. |
| test-14 | Does not blindly retry an ambiguous side-effecting POST; introduces or requires idempotency/deduplication/reconciliation before retrying. |
| test-15 | Addresses bounded queues/concurrency, admission control/backpressure/load shedding, and observability; does not treat retries as an overload solution. |
| test-16 | Asks what the limiter protects (abuse, cost, contractual quota, safety) before answering; does not treat "rate limiter" as automatically an availability control that may fail open. Fails closed where the limit guards a critical invariant; if degrading, bounds it and makes it observable. |
| test-17 | Identifies that lease expiry does not stop a stalled holder; requires a fencing or generation token **checked by the protected resource**, or an equivalent conditional write. Does not accept a longer TTL as the fix. |
| test-18 | Uses incident framing: separates observed facts, hypotheses, and the amplification mechanism sustaining the failure after its trigger passed (retries, queue backlog, recovery work). Proposes bounded containment — shed, cap retries, drop stale work — before proposing more retries, replay, or failover. |
| test-19 | Does not invoke the skill; adds the docstring. |
| test-20 | Identifies the dual-write gap and proposes an outbox or equivalent, **and** pairs it with an idempotent consumer or inbox because the relay can republish. Does not claim exactly-once without naming the boundary it holds over. |
| test-21 | Does not invoke the skill; performs only the requested refactor. |

## Cross-cutting graders

A strong response should also satisfy these properties when relevant:

- Does not expose private chain-of-thought.
- Does not claim tests are VERIFIED unless executed evidence exists.
- Prefers existing proven SDK/framework/platform resilience over duplicate custom mechanisms.
- Uses end-to-end deadlines rather than relying only on per-socket timeouts for user-visible latency budgets.
- Avoids retry multiplication across layers.
- Does not retry non-idempotent or ambiguous writes without duplicate protection.
- Does not classify all 4xx or 429 responses identically without dependency-contract reasoning.
- Does not add circuit breakers, queues, failover, metrics infrastructure, or locks merely because the skill was invoked.
- Distinguishes a known failure from an unknown outcome after a side-effecting timeout.
- Classifies a control by the invariant it protects, not by its mechanism name, before deciding fail-open versus fail-closed.
- Treats recovery actions (retry, replay, failover, rebuild, drain) as load sources that need their own bounds.
- Bounds queue age, not only queue depth, where stale work is possible.
- Keeps high-cardinality identifiers (tenant, user, idempotency key, raw URL) out of metric labels.
- Keeps security/authentication/authorization failure closed.
- Preserves the user's requested output format for review/design tasks.
