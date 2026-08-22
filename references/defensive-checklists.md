# Defensive Checklists

Companion to `SKILL.md`. Use these when the change is Tier 2 or Tier 3, or when a
control is unfamiliar. Failure classification lives in `references/failure-taxonomy.md`;
verification, runtime signals, and rollout gates live in `references/verification-and-chaos.md`. Each item is a question to answer, not a mandate to
implement. An item that does not apply to the change is answered "not applicable
because ..." and dropped.

## Deadlines and Timeouts

- [ ] Does the operation have an overall deadline, set by the caller or inherited from one?
- [ ] Is the remaining budget propagated to every downstream call, rather than each layer starting a fresh full-length timer?
- [ ] Are connect, pool-acquisition, TLS handshake, read, and write bounded separately where the client supports it, or is it documented why the client cannot split them? (httpx, for example, shares one value between TCP connect and the TLS handshake.)
- [ ] Is the per-attempt timeout smaller than the overall deadline, so retries can actually occur?
- [ ] Are streaming and long-poll reads bounded by an idle timeout, not only a total timeout?
- [ ] Do background, cleanup, and shutdown paths have their own bounded deadline instead of blocking forever?
- [ ] Is a client-side timeout paired with server-side cancellation, so an abandoned request stops consuming resources?

## Retries

- [ ] Is exactly one layer in the call chain responsible for retrying this operation?
- [ ] Have nested retries across SDK, client wrapper, service, proxy, and worker been checked for multiplication?
- [ ] Is the failure classified as transient before a retry is attempted, rather than retrying every exception?
- [ ] Is the operation repeat-safe, or protected by idempotency, before any retried write?
- [ ] Is there a maximum attempt count *and* a deadline check, so retries stop on whichever comes first?
- [ ] Does the backoff cap its delay and include jitter?
- [ ] Are server retry hints such as `Retry-After` honored, and bounded so a hostile or broken value cannot stall the caller?
- [ ] Are permanent failures (validation, auth, not-found, unsupported) excluded from retry?
- [ ] Does retry behavior avoid amplifying load during a dependency-wide outage?

## Circuit Breakers and Load Shedding

- [ ] Is there evidence that repeated failure would amplify load or exhaust a resource? If not, omit the breaker.
- [ ] Which failures count toward opening: timeouts, 5xx, connection errors? Are 4xx excluded from counting *and* kept from resetting the counter? A client error that zeroes the failure count lets an alternating 5xx/4xx dependency hold the breaker closed forever.
- [ ] Can a probe that is cancelled mid-flight leave the breaker half-open with no timer able to re-arm it?
- [ ] What is the open duration, and what limits probe traffic in the half-open state?
- [ ] What happens to callers while the breaker is open: error, fallback, or queue? Is that path bounded?
- [ ] Is breaker state observable, and does it recover without manual intervention?
- [ ] Is the breaker scoped correctly (per host, per endpoint, per tenant) so one bad key cannot trip the whole dependency?

## Idempotency and Effect-Once Writes

- [ ] Is the idempotency key scoped to the authenticated actor, tenant, operation, and resource as required?
- [ ] Is the key bound to a canonical fingerprint of the request, so the same key with different semantics conflicts instead of silently returning the first result?
- [ ] Is the key claimed atomically with the state transition (unique constraint, conditional insert, or transaction), not checked-then-written?
- [ ] Are the in-progress, completed, failed, expired, and abandoned states all defined and reachable?
- [ ] What happens when a process crashes between claiming the key and committing the effect? Is there a reconciliation or expiry path for that gap?
- [ ] Is deduplication state retained at least as long as the duplicate-delivery and retry window?
- [ ] For effects in another system, is there an outbox, inbox, saga, provider idempotency key, or reconciliation job?
- [ ] If an outbox is used, is the consumer also idempotent or backed by an inbox ledger? The relay can republish after a crash between publish and mark-published, so the producer-side fix alone is incomplete.
- [ ] Does any claim of exactly-once name the exact durability and side-effect boundary it holds over, rather than implying it covers external effects such as email, payment, or object-store writes?
- [ ] Is the guarantee stated accurately — usually at-least-once delivery with atomicity only over the state the broker itself owns — rather than claimed as exactly-once?

## Ambiguous Outcomes and Partial Success

- [ ] For each write, what does the caller do when the response is a timeout or a dropped connection?
- [ ] Is the resolution a status lookup, an idempotency-key replay, or reconciliation, rather than a blind repeat?
- [ ] Can a multi-item operation partially succeed? If so, is per-item status returned instead of a single success or failure?
- [ ] Is there a compensating action or reconciliation for the items that failed?
- [ ] Does a partial result get stored, cached, or forwarded in a way that later reads as complete?

## Concurrency and Shared State

- [ ] Is every read-modify-write sequence protected by a transaction, unique constraint, compare-and-swap, lock, or lease?
- [ ] Are invariants enforced by the data store rather than by timing assumptions or optimistic ordering?
- [ ] Is parallelism bounded overall and per contended key?
- [ ] Are connections, sessions, clients, transactions, and file handles used within their documented ownership and thread- or task-safety rules?
- [ ] Do leases have a fencing token or generation number, so a stalled holder cannot act after expiry?
- [ ] Does the protected resource itself reject writes carrying a fence below the current generation? A token that nothing checks is decorative — lease expiry does not inform the paused holder.
- [ ] Are lock hold times bounded, and is remote I/O kept out of critical sections where possible?
- [ ] Is deadlock avoided by consistent acquisition order or by lock timeouts?

## Capacity, Bounds, and Backpressure

- [ ] Are queues, channels, buffers, and pools bounded, with a defined behavior on full: block with timeout, reject, shed, or spill?
- [ ] Are payload size, result-set size, batch size, page count, and fan-out width bounded?
- [ ] Is recursion depth bounded, and is unbounded recursion converted to iteration where it can be driven by input?
- [ ] Is memory bounded for streaming, buffering, and accumulation paths, rather than reading an entire response into memory?
- [ ] Is the age of the oldest useful work bounded, not only queue depth? Depth can look healthy while nothing queued is still worth processing.
- [ ] Is work that has passed its deadline, TTL, lease, or version dropped rather than processed?
- [ ] Is backpressure applied before saturation, with deliberate rejection, deferral, sampling, or shedding?
- [ ] Do rejected requests receive a clear signal (status, retry hint) so callers do not hot-loop?
- [ ] Can the fallback or failover target absorb the traffic that would be redirected to it?
- [ ] For each recovery mechanism — retry, replay, failover, cache rebuild, backlog drain, autoscaling — does it add work to an already-failing system, and what bounds that work? Overload can sustain itself after its original trigger is gone.
- [ ] Under sustained overload, is there a path that reduces optional work, stops retries, and sheds stale requests, rather than only queueing harder?

## Cancellation and Shutdown

- [ ] Is cancellation propagated to downstream calls rather than being caught and treated as an ordinary failure?
- [ ] On cancellation, are owned resources released and partially-applied state either committed consistently or rolled back?
- [ ] On shutdown: does the process stop accepting new work, stop spawning children, drain or checkpoint in-flight work within a deadline, release leases, and close resources?
- [ ] Does readiness flip before the drain begins, so traffic stops arriving?
- [ ] Is a hard-kill path considered — can the system restart cleanly from whatever state a `SIGKILL` leaves behind?

## Errors and Degradation

- [ ] Are expected domain outcomes (no data, denied, conflict) represented separately from operational failures?
- [ ] Is the internal cause preserved for diagnosis while the external error stays stable and non-sensitive?
- [ ] Is there any path that returns ordinary success after an unhandled internal failure?
- [ ] For each broad catch: does it classify, record, convert, compensate, degrade, or re-raise? A broad catch that only continues is a defect.
- [ ] For each fallback: does it preserve the same authorization, tenancy, privacy, and integrity constraints as the primary path?
- [ ] Is the fallback bounded, explicitly labelled in the result, observable in telemetry, tested, and recoverable?
- [ ] Is degraded output kept out of caches, or cached under distinct semantics with conservative expiry and explicit metadata?
- [ ] Can degraded or stale output reach a privileged, irreversible, or financial decision? If so, that path fails closed instead.

## Untrusted Input and Trust Boundaries

- [ ] Is authority checked at the authoritative boundary, before expensive or privileged work?
- [ ] Is the same authorization applied unchanged on retry, cache-hit, fallback, replay, and recovery paths?
- [ ] Are shape, type, size, count, encoding, and semantic ranges validated, not just parsed?
- [ ] Are tenancy and scope derived from verified server-side context rather than from request-supplied fields?
- [ ] Is dependency output — including from internal services — validated before it affects state or privilege?
- [ ] Are decompression, deserialization, redirect following, and file parsing bounded against expansion and traversal?
- [ ] Are outbound requests derived from user input restricted against internal network access?

## Caches

- [ ] Does the cache key include every dimension that changes the correct answer: tenant, principal or authorization scope, schema or code version, locale, and representation?
- [ ] Is a cache read treated as advisory, so a miss or an error falls through to a safe, bounded recomputation?
- [ ] Is cache failure ever allowed to bypass an authorization check? It must not be.
- [ ] Is negative caching bounded, and does it avoid pinning a transient failure for a long TTL?
- [ ] Is stampede protection needed (single-flight, jittered TTL, early refresh), given the recomputation cost?
- [ ] Are invalidation and staleness bounds defined, and is stale data labelled when served?

## Queues, Workers, and Webhooks

- [ ] Is acknowledgement deferred until the required durable effect or checkpoint is complete?
- [ ] Is the consumer safe against redelivery — deduplication, idempotent effect, or a transactional inbox?
- [ ] Are visibility timeout or lease duration longer than realistic processing time, and is the lease extended for long work?
- [ ] Is there a maximum attempt count with dead-lettering, and is the dead-letter queue monitored and drainable?
- [ ] Is poison-message handling defined, so one bad payload cannot stall the partition or the worker pool?
- [ ] Where ordering matters, is it actually guaranteed by the transport and preserved by the consumer's concurrency model?
- [ ] Are webhook signatures verified before any tenant resolution, parsing, or side effect?
- [ ] Is webhook delivery deduplicated by provider event id, with replay-window and timestamp checks?
- [ ] Does the webhook endpoint respond within the provider's timeout, deferring slow work to a durable queue?

## Model, Tool, and Agent Boundaries

- [ ] Is model and tool output treated as untrusted data rather than as instructions or as validated structure?
- [ ] Are output schemas revalidated before use, and is authorization re-checked at execution time rather than at planning time?
- [ ] Are steps, tool calls, tokens, wall-clock time, fan-out width, and spend all bounded, with a stop rule that does not depend on the model deciding to stop?
- [ ] Do destructive, privileged, or irreversible tool actions require approval bound to the exact resolved action and arguments?
- [ ] Is retrieved or fetched content prevented from escalating privilege or redirecting the agent's authority?
- [ ] Are partial, refused, truncated, and failed model outcomes distinguished from empty success?

## Observability

- [ ] Do logs carry enough correlation context (request, tenant, operation, attempt) to reconstruct a failure?
- [ ] Are secrets, credentials, tokens, personal data, and payload bodies excluded from logs, traces, and error messages?
- [ ] Is metric cardinality bounded — no unbounded identifiers as label values?
- [ ] Are degradation, fallback, shed, retry-exhaustion, breaker-open, and dead-letter events all countable?
- [ ] Are privileged and irreversible effects audited where policy requires it, with append-only semantics?
- [ ] Does readiness reflect the ability to serve safely, and liveness avoid restarting a healthy process during a dependency outage?

## Failure-Path Tests

Prefer deterministic clocks, injected randomness, controllable fakes, and
synchronization primitives over sleeps. A test that passes by timing luck is not
evidence. Report each item as `verified`, `reasoned_not_run`, `blocked`, or
`not_applicable` — a check that could not run is never a pass.

- [ ] Success with representative input, and valid absence returning an explicit no-data result.
- [ ] Invalid, malformed, wrong-type, oversized, and excessively-nested input rejected with a stable error.
- [ ] Unauthenticated and unauthorized requests denied, including on cache-hit, fallback, and replay paths.
- [ ] Timeout on a dependency: the caller stops within the deadline and reports the right class.
- [ ] Transient failure followed by success: retried and resolved within the attempt and deadline budget.
- [ ] Permanent failure: not retried, surfaced promptly.
- [ ] Retry budget exhausted: the correct terminal error, no partial effect left behind.
- [ ] Duplicate request with the same idempotency key: one effect, consistent response.
- [ ] Same key with different request semantics: conflict, not a silent replay.
- [ ] Concurrent requests on the same key or resource: the invariant holds under real parallelism.
- [ ] Ambiguous write outcome (timeout after the effect committed): resolved without duplicating the effect.
- [ ] Crash or restart between claiming a key and committing: recovery leaves a consistent state.
- [ ] Partial multi-item result: per-item status returned, failed items reconciled or compensated.
- [ ] Fallback path exercised: security context preserved, result labelled degraded, not cached as ordinary success.
- [ ] Stale or degraded data blocked from driving a privileged or irreversible decision.
- [ ] Cancellation mid-flight: downstream work stops, resources released, committed state preserved.
- [ ] Graceful shutdown during in-flight work: drained or checkpointed, leases released.
- [ ] Worker lease expiry and redelivery: no duplicate effect, no lost message.
- [ ] Poison message: dead-lettered, pipeline continues.
- [ ] Bounds enforced: full queue, oversized payload, excessive fan-out, deep recursion, large result set.
- [ ] Backpressure: overload produces deliberate rejection or shedding rather than collapse.
- [ ] Stale work past its deadline or TTL is dropped, not processed at capacity cost.
- [ ] Stale lease holder resumes after a new holder acquired the lease: its write is rejected by fence.
- [ ] Cache failure: treated as a miss where safe, never as an authorization bypass.
- [ ] Logs and metrics from failure paths contain no secrets and no unbounded cardinality.
