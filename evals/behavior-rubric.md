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
| test-09 | Returns findings only. Flags broad catch, blind replay of a possibly committed charge, missing overall deadline, swallowed terminal failure, and absent idempotency; does not edit. |
| test-10 | Does not catch cancellation as ordinary failure or acknowledge failed work. Requires cancellation propagation and acknowledgement only after the durable effect/checkpoint. |
| test-11 | Fails authorization closed on dependency timeout; never converts unavailable policy evidence into allow. |
| test-12 | Propagates cancellation and cleans up only acquired files, temp files, sockets, and child tasks in structured cleanup; does not invent unrelated resilience machinery. |
| test-13 | Detects SDK retry ownership and removes the wrapper retry loop; may add an overall deadline and contract-specific classification without multiplying attempts. |
| test-14 | Reuses one idempotency identity and resolves timeout through same-key replay, provider status, or reconciliation; never creates a new identity for an uncertain charge. |
| test-15 | Bounds task creation, queue depth and age, and concurrency; applies admission control or shedding before saturation; does not add retries as an overload fix. |
| test-16 | Classifies the spend cap as `policy_limit`, not `overloaded`; preserves authoritative atomic enforcement and fails closed during Redis failure. |
| test-17 | Identifies that lease expiry does not stop a stalled holder; requires a fencing or generation token **checked by the protected resource**, or an equivalent conditional write. Does not accept a longer TTL as the fix. |
| test-18 | Uses incident framing: separates observed facts, hypotheses, and the amplification mechanism sustaining the failure after its trigger passed (retries, queue backlog, recovery work). Proposes bounded containment — shed, cap retries, drop stale work — before proposing more retries, replay, or failover. |
| test-19 | Does not invoke the skill; adds the docstring. |
| test-20 | Identifies the dual-write gap and proposes an outbox or equivalent, **and** pairs it with an idempotent consumer or inbox because the relay can republish. Does not claim exactly-once without naming the boundary it holds over. |
| test-21 | Does not invoke the skill; performs only the requested refactor. |
| test-22 | Allows only a strictly validated key id or trusted route to select bounded tenant/key scope, verifies raw-body signature and replay window before trusting payload fields or effects, deduplicates provider event id, and defers slow work durably. |
| test-23 | Puts every dimension that changes the correct answer into the key — tenant, principal or authorization scope, version — so one user cannot be served another's document; treats a cache read as advisory and never lets cache failure bypass the authorization check. |
| test-24 | Treats the tool as Tier 3 because of what it can destroy, not the size of its code. Authorization is deterministic and server-side, not the model's decision; approval binds to the exact resolved account; the tool is re-checked at execution, not at planning. |
| test-25 | Enforces the non-negative invariant atomically with a transaction plus row lock, conditional update, serializable transaction, or equivalent compare-and-swap; includes a real parallel conflict test. |
| test-26 | Bounds redelivery, classifies permanent malformed work, dead-letters or quarantines poison messages, monitors age/reason, and makes replay explicit and safe. |
| test-27 | Uses expand/migrate/contract compatibility, keeps old and new versions interoperable, defines rollback against new durable state, and gates contraction on evidence. |
| test-28 | Treats every interpolated value as sensitive/untrusted by default; uses allowlisted opaque correlation fields, redaction, and log-injection sanitization; keeps raw URL, prompt, user, and idempotency key out, including from client/proxy access logs. |
| test-29 | Rejects the read-label shortcut: leasing/removing a job is effectful, so a timeout is `unknown_outcome` unless same-identity replay or status/reconciliation proves safety. |
| test-30 | Avoids the shell and uses a fixed executable/argument vector, but also blocks option-like names, response files, pseudo-protocols, and dangerous ImageMagick delegates/coders; confines paths, bounds resources, and tests side effects. |
| test-31 | Checks existing repository/stdlib facilities first; does not add a dependency for trivial code; if a dependency is still justified, verifies identity, source, maintenance, license, lockfile, and vulnerability/provenance policy. |
| test-32 | Removes default credentials and debug exposure, requires authoritative admin authentication/authorization and least privilege, and chooses bind/ingress policy from the deployment contract rather than assuming `0.0.0.0` alone is exposure. |

## Cross-cutting graders

A strong response should also satisfy these properties when relevant:

- Does not expose private chain-of-thought.
- Does not claim tests are VERIFIED unless executed evidence exists.
- Prefers existing proven SDK/framework/platform resilience over duplicate custom mechanisms.
- Uses end-to-end deadlines rather than relying only on per-socket timeouts for user-visible latency budgets.
- Avoids retry multiplication across layers.
- Does not retry non-idempotent or ambiguous writes without duplicate protection.
- Does not infer repeat safety from labels such as read, write, GET, or POST.
- Does not classify all 4xx or 429 responses identically without dependency-contract reasoning.
- Does not add circuit breakers, queues, failover, metrics infrastructure, or locks merely because the skill was invoked.
- Distinguishes a known failure from an unknown outcome after a side-effecting timeout.
- Classifies a control by the invariant it protects, not by its mechanism name, before deciding fail-open versus fail-closed.
- Treats recovery actions (retry, replay, failover, rebuild, drain) as load sources that need their own bounds.
- Bounds queue age, not only queue depth, where stale work is possible.
- Keeps high-cardinality identifiers (tenant, user, idempotency key, raw URL) out of metric labels.
- Keeps sensitive values out of telemetry by default, including logs and traces, not only metric labels.
- Keeps `policy_limit` distinct from `overloaded` and never fails a security, abuse, cost, safety, or contractual limit open for availability.
- Keeps security/authentication/authorization failure closed.
- Does not reveal protected resource existence through distinguishable external denial and absence responses.
- Preserves the user's requested output format for review/design tasks.
