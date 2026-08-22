---
name: defensive-design
description: Use when designing, implementing, or reviewing code that crosses trust boundaries, calls external dependencies, mutates durable state, runs concurrently, handles untrusted input, or consumes finite resources. Applies to production-readiness, resilience, timeouts, retries, idempotency, backpressure, rate limiting, graceful degradation, failover, consistency, webhooks, queues, databases, caches, files, LLM or tool calls, happy-path-only drafts, and debugging a production incident or cascading failure. Skip for deterministic in-memory helpers with no meaningful external effects.
---

# Defensive Design

## Objective

Build the smallest verified design that remains safe, bounded, observable, and recoverable when inputs, dependencies, timing, concurrency, or infrastructure fail.

Assume that inputs can be malformed or hostile, dependencies can be slow or partially successful, writes can be duplicated after ambiguous outcomes, processes can restart at any instruction, and every queue, pool, loop, budget, and deadline is finite.

Be pessimistic at boundaries and economical in implementation. Defensive complexity is also a failure mode.

## Non-Negotiable Invariants

1. **Security and integrity fail closed.** Authentication, authorization, tenancy, privacy, signatures, destructive actions, and irreversible financial effects never gain a permissive fallback.
2. **Availability degrades only through a safe explicit path.** A fallback must preserve the same critical constraints, be bounded, expose its degraded state, and have a recovery path.
3. **All work is bounded.** Every wait, retry, loop, queue, batch, fan-out, recursion path, and resource allocation needs a limit or inherited budget.
4. **Retried writes need effect-once behavior.** Use idempotency, atomic deduplication, transactional state, provider idempotency, or reconciliation. Do not casually claim exactly-once delivery.
5. **Outcomes remain distinct.** No-data, invalid, denied, conflict, partial, degraded, cancelled, and failed are not interchangeable with `None`, `False`, an empty collection, or generic success.
6. **Untrusted context stays untrusted.** Validate user input, dependency output, retrieved content, model output, webhook payloads, and tool results before they affect state or privilege.
7. **Repository evidence outranks generic advice.** Reuse existing contracts and cross-cutting infrastructure before creating new wrappers or frameworks.
8. **Claims carry an evidence state.** Every verification or completion claim is labelled `verified` (actually executed or authoritative runtime output inspected), `reasoned_not_run` (follows from code inspection, not executed), `blocked` (appropriate but unavailable — no environment, credentials, or tooling), or `not_applicable`. Confidence is not evidence.
9. **Recovery must not amplify failure.** Retries, replays, failover, cache rebuilds, backlog drains, compensations, and autoscaling all create work. Before adding one, answer: does this add load to an already-failing system, and what bounds it? Overload can sustain itself after its original trigger is gone.

A quota, cache, fallback, or rate limiter is not automatically an availability control. Classify whether it protects security, abuse, cost, contractual limits, or integrity before deciding how it fails.

## Apply Proportionally

Use the highest applicable tier:

| Tier | Typical change | Required depth |
|---|---|---|
| 0: Local | Pure deterministic in-memory logic | Clear contract, precise errors, focused tests |
| 1: Boundary | External read, parser, upload, cache, remote query | Tier 0 plus validation, limits, deadline, failure contract, safe logging |
| 2: Stateful | Durable write, queue, webhook, concurrency, worker | Tier 1 plus idempotency, atomicity, race control, retry ownership, recovery tests |
| 3: Critical | Auth, tenancy, privacy, billing, destructive or irreversible action | Tier 2 plus fail-closed behavior, auditability, reconciliation or rollback, strong negative and concurrency tests |

Tier follows consequence, not size. A five-line cross-tenant authorization check is Tier 3; a thousand-line deterministic formatter over trusted internal data stays Tier 0.

Do not add retries, breakers, failover, or telemetry to a pure helper without a real failure surface.

For Tier 2 or Tier 3 work, or whenever a control is unfamiliar, read `references/defensive-checklists.md` before implementing.

## Workflow

### 1. Establish the Contract

Before editing:

- Read repository instructions, architecture, public contracts, configuration, neighboring code, and relevant tests.
- Translate the request into externally observable acceptance criteria.
- Define full success, no-data, denial, conflict, partial success, degradation, cancellation, and failure only where applicable.
- Identify critical invariants, side effects, commit points, compatibility requirements, and latency, cost, size, and retry budgets.
- Find existing facilities for errors, retries, timeouts, idempotency, logging, metrics, tracing, auditing, health checks, and shutdown.
- Keep scope focused. Do not mix defensive work with unrelated cleanup.

Do not invent repository paths, helpers, configuration keys, dependency behavior, or test results.

### 2. Map Material Failure Modes

Trace input to final effect and identify:

- Trust and authorization boundaries.
- Remote dependencies and every timeout or retry layer.
- Durable state transitions and transaction boundaries.
- Race windows, locks, leases, shared resources, and cancellation points.
- Duplicate delivery, ambiguous write outcomes, restart points, and partial success.
- Queues, pools, caches, fan-out, fallbacks, and work age.
- Recovery mechanisms themselves: retries, replays, failover, cache rebuilds, backlog drains, autoscaling. Each is a load source during the incident it is meant to fix.

Analyze failures that are severe, plausible, difficult to detect, or capable of violating an invariant. Do not enumerate every theoretical event.

For non-trivial work, use this compact table:

| Operation | Failure | Class | Invariant at risk | Required behavior | Detection and test |
|---|---|---|---|---|---|

### 3. Classify Before Handling

| Failure class | Default behavior |
|---|---|
| Valid absence (`absence`) | Return an explicit no-data result. No retry. |
| Invalid input or contract (`invalid`) | Reject with a stable error. No retry. |
| Unauthenticated or unauthorized (`unauthenticated`, `unauthorized`) | Fail closed. No fallback that broadens access. |
| Conflict or stale version (`conflict`) | Return conflict, or perform a bounded compare-and-retry only when designed for it. |
| Known transient dependency failure (`transient_dependency`) | Retry only when repeat-safe and the overall deadline allows it. |
| Overload or saturation (`overloaded`) | Backpressure, bounded queueing, load shedding, or retry hint. Avoid retry amplification. |
| Ambiguous write outcome (`unknown_outcome`) | Resolve through idempotency lookup, provider status, or reconciliation. Never blindly repeat the effect. |
| Partial success (`partial_success`) | Return explicit item-level or typed partial state, then reconcile or compensate as required. |
| Permanent dependency or configuration failure (`permanent_dependency`) | Fail fast and avoid retry storms. Affect readiness when safe service is impossible. |
| Stale or superseded work (`stale_work`) | Drop or cancel it. Work past its usefulness deadline, TTL, lease, or version consumes capacity without producing value. Do not retry it. |
| Cancellation or deadline expiry (`cancelled`) | Stop new work, clean up owned resources, preserve committed state, and propagate cancellation. |
| Internal invariant violation (`invariant_violation`) | Stop the unsafe operation, preserve evidence, and surface an internal failure. |

Backticked names are canonical; `references/failure-taxonomy.md` holds the full table, the retry and outcome-certainty rules, and the failure envelope.

A broad catch is acceptable only at a deliberate boundary that classifies, records, converts, compensates, degrades, or re-raises the error. Never catch broadly merely to continue.

### 4. Choose the Smallest Effective Controls

Every added mechanism must answer:

1. Which identified failure does it mitigate?
2. Which invariant does it preserve?
3. How is it bounded and observable?
4. How will it be tested?

If those answers are weak, omit or simplify it.

### 5. Implement Failure Behavior With the Main Path

- Validate authority, shape, size, and semantics before expensive or privileged work.
- Keep security checks at the authoritative boundary and apply them unchanged to retries, caches, fallbacks, and recovery.
- Use an overall deadline plus bounded per-attempt timeouts for remote work.
- Assign one retry owner per call chain. Retry only known transient failures, with capped backoff and jitter, when the operation is repeat-safe.
- Bind idempotency keys to authenticated scope and canonical request semantics. Claim them atomically with the state transition or provide reconciliation for crash gaps.
- Enforce concurrency invariants with transactions, constraints, compare-and-swap, locks, leases, or fencing, not timing assumptions. A lease bounds who *should* own a resource; it does not prove a stalled former holder has stopped. Where a stale holder can still mutate shared or external state, the protected resource must itself reject writes below the current fencing or generation number. An unchecked token is decorative.
- Bound task creation, queue depth *and queue age*, batches, payloads, result sets, retries, fan-out, recursion, memory, and connection use. Depth alone hides the case where nothing in the queue is still useful.
- Preserve cancellation and structured cleanup. Do not swallow cancellation as ordinary failure.
- Represent partial, degraded, stale, denied, and failed outcomes explicitly.
- Log structured diagnostic data without secrets. Keep metric labels bounded — operation, dependency, status family, failure class, retryability. Tenant, user, idempotency key, raw URL, and prompt text belong in logs or traces under policy, never as metric dimensions. Audit privileged or irreversible effects where policy requires it.
- Reuse repository-native abstractions. Do not create a second resilience stack for one call site.

When implementation is requested, provide complete in-scope code rather than placeholders. Do not weaken tests, broaden permissions, silently reduce scope, or claim production readiness for unverified behavior.

### 6. Verify the Final State

After the last change that could affect behavior, run the relevant checks for:

- Expected success and valid absence.
- Invalid, malformed, oversized, denied, and unauthorized input.
- Timeout, transient failure, permanent failure, and exhausted retry budget.
- Duplicate and concurrent requests.
- Ambiguous write result and idempotent replay.
- Partial response, fallback, stale data, and recovery.
- Cancellation, shutdown, restart, lease expiry, or worker redelivery.
- Queue, pool, payload, fan-out, recursion, and memory limits.
- Preservation of auth, tenancy, privacy, integrity, and side-effect invariants on fallback paths.

Prefer deterministic clocks, injected randomness, controllable fakes, and synchronization primitives over sleep-based timing tests.

Report exact commands and outcomes. Label every claim with its evidence state — `verified`, `reasoned_not_run`, `blocked`, `not_applicable` — and never imply an unrun check passed.

Verification depth scales with tier. Tier 0/1 is deterministic tests, malformed input, timeout, and cancellation. Tier 2 adds duplicate delivery, concurrency, ambiguous write outcome, redelivery, rollback, and dependency fault injection. Tier 3 adds negative authorization and tenancy, fail-closed dependency outage, approval binding, and a recovery drill. Production chaos is optional, and only with a stated steady-state hypothesis, a bounded blast radius, and an automatic stop condition. See `references/verification-and-chaos.md`.

## Control Rules

### Deadlines and Retries

- Use an overall operation deadline and propagate the remaining budget.
- Bound connect, pool acquisition, read, write, and per-attempt time where supported.
- Stop on cancellation, exhausted deadline, exhausted attempts, or evidence of permanent failure.
- Respect safe server retry hints such as `Retry-After`.
- Avoid nested retry multiplication across clients, services, proxies, and workers.
- A circuit breaker is justified only when repeated remote failure would amplify load or exhaust resources. Define counted failures, open and half-open behavior, probe limits, observability, and fallback.

### State and Idempotency

- Scope keys to the actor, tenant, operation, and resource as required.
- Bind keys to a canonical request fingerprint. Same key plus different semantics must conflict.
- Define in-progress, completed, failed, expired, and abandoned states.
- Retain deduplication state for the full duplicate-delivery or retry window.
- For cross-system effects, use an outbox, inbox, saga, provider idempotency key, or reconciliation when one transaction is impossible.
- An outbox closes the dual-write gap on the *producer* side only. The relay can still publish a record twice after a crash between publish and mark-published, so the consumer stays idempotent or keeps an inbox ledger. Outbox and inbox are a pair, not alternatives.
- Never write "exactly once" without naming the exact durability and side-effect boundary it holds over. Broker-level exactly-once processing does not make an email, payment, object-store write, or outbound HTTP call exactly once.
- State the actual guarantee, usually at-least-once delivery with effect-once processing for a bounded window.

### Concurrency and Capacity

- Bound parallelism and per-key contention.
- Protect read-modify-write sequences atomically.
- Follow ownership and thread or task-safety rules for sessions, clients, transactions, and handles.
- On shutdown, stop accepting work, stop spawning children, drain or checkpoint bounded work, release leases, and close resources within a deadline.
- Apply backpressure before saturation. Reject, defer, sample, or shed work deliberately. Prefer rejecting at admission over accepting work that cannot finish before it stops being useful.
- Bound the age of the oldest useful work, not just queue depth. Shed stale work first.
- Under overload: reduce optional work, sharply constrain or stop retries, shed low-priority and stale work, preserve critical capacity, and expose the overloaded state.
- Ensure fallback capacity can handle failover traffic.

### Errors and Degradation

- Keep expected domain outcomes separate from operational failures.
- Preserve internal causes while exposing stable, non-sensitive external errors.
- Never return ordinary success after an unhandled internal failure.
- A fallback is valid only if it preserves critical invariants, is semantically acceptable, bounded, explicit, observable, tested, and recoverable.
- Do not cache degraded output as ordinary success. If intentional, use explicit metadata, separate semantics, and conservative expiry.
- Degraded or stale output must not silently drive privileged or irreversible decisions.

### External, Cache, Queue, and Agent Boundaries

- A successful transport does not prove semantic success. Validate status and payload.
- Cache keys must include every tenant, authorization, version, locale, and representation dimension needed to prevent cross-context reuse.
- Treat cache failure as a miss only when recomputation is safe and bounded.
- Queue consumers acknowledge only after the required durable effect or checkpoint. Define max attempts, leases, deduplication, poison handling, dead-lettering, and replay safety.
- Treat LLM and tool output as untrusted. Revalidate schemas and authorization at execution, bound steps, tokens, calls, time, fan-out, and spend, and require exact-action approval for destructive or privileged operations.

More detailed control and test checklists are in `references/defensive-checklists.md`.

## Output Contract

Adapt to the task instead of forcing one template.

### Review

Lead with findings ordered by severity. Each finding names the invariant at risk, a concrete triggering scenario, evidence and location, impact, the smallest safe remediation, and the missing verification. Do not bury concrete defects under a generic architecture essay, and do not pad the list with speculative defects the code does not support.

| Severity | Meaning |
|---|---|
| Blocker | A critical invariant can be violated: auth, tenancy, integrity, duplicate financial or destructive effect, data corruption, uncontrolled privileged action. |
| High | Credible outage or cascading failure, durable inconsistency, unbounded resource growth, or unrecoverable operational state. |
| Medium | Failure handling, observability, or recovery is materially incomplete, but the critical invariant still holds. |
| Low | Hardening or maintainability with limited immediate failure impact. |

A few defensible findings beat a long speculative list.

### Design

Provide the contract and critical invariants, material failure table, selected controls and rejected alternatives, state and fallback behavior, recovery, verification, rollout, and observability.

### Implementation

Provide a brief contract and risk summary, focused repository-native changes, relevant failure-path tests, exact verification results, and residual risks or skipped checks.

### Incident or Debugging

Keep these separate and labelled: observed facts, hypotheses, the amplification mechanism sustaining the failure, immediate containment, corrective design, and the evidence needed to confirm recovery. Treat "fail over", "replay", "restart everything", "rebuild the cache", and "drain the backlog" as changes that need their own failure model and blast-radius limit before execution.

### Small Change

Apply relevant rules without ceremony. Report changed behavior and verification in a few precise sentences.

## Stop and Reconsider When

- A timeout on a side-effecting call is treated as proof nothing happened.
- Independent retry loops exist at more than one layer of the same call chain.
- Retries have no overall deadline or attempt budget.
- A security, abuse, cost, or safety control is labelled "availability" to justify failing open.
- A queue has unbounded age or redelivery, or no poison-message path.
- An outbox is called exactly-once without consumer deduplication.
- A lease guards external mutation and nothing rejects the stale holder.
- A fallback widens authorization, or silently feeds an authoritative or irreversible decision.
- A model or its tool output decides its own authorization or scope.
- Shared state relies only on process-local locking.
- Metrics carry unbounded label values.
- Production readiness is asserted without failure-path evidence, or tests are claimed without having been run.

## Completion Gate

Do not declare completion until the applicable statements are true:

- Untrusted boundaries validate authority, shape, semantics, and size.
- Critical boundaries fail closed.
- Remote waits have an effective timeout or inherited deadline.
- Loops, retries, queues, batches, fan-out, recursion, and resource use are bounded.
- One layer owns retries and retries only classified repeat-safe failures.
- Duplicate-prone writes are effect-once or reconciled after ambiguous outcomes.
- Concurrency invariants are enforced atomically.
- Cancellation and shutdown preserve committed state and release owned resources.
- Partial, degraded, stale, denied, no-data, cancelled, and failed outcomes remain distinct.
- Fallbacks preserve the same security context and cannot silently become authoritative.
- Logs, metrics, traces, and audits are useful without leaking sensitive data.
- Queue depth and queue age are bounded, and stale work is dropped rather than processed.
- Leases that guard shared or external state are fenced, and the resource rejects stale generations.
- Recovery paths — retry, replay, failover, rebuild, drain — are bounded and cannot amplify the failure they respond to.
- Failure-path checks ran against the final relevant code state.
- Every completion claim carries an evidence state, and nothing unrun is reported as passing.

The goal is not maximum machinery. The goal is minimum verified protection against the failures that can actually violate the contract.

## Package References

When a concrete Python outbound-HTTP example would help, inspect `references/resilient_http_example.py`. Treat it as an illustrative pattern, not a universal template. Reuse only the mechanisms justified by the current task.

`references/failure-taxonomy.md` holds the full failure-class table, the failure envelope, and how to express these classes over HTTP. `references/verification-and-chaos.md` holds the per-surface verification matrix, the runtime signals that reveal amplification, chaos-experiment gates, and the rollout/rollback contract. Read them when the work is Tier 2 or Tier 3, or when a control is unfamiliar.

For maintainers, trigger evals live in `evals/defensive-design.prompts.csv`, behavior expectations in `evals/behavior-rubric.md`, and deterministic regression checks for the Python reference in `scripts/verify_reference.py`.
