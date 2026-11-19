# Verification, Signals, and Rollout

Companion to `SKILL.md`. Use when choosing failure-path tests, and for Tier 2 and
Tier 3 work: what to watch at runtime and what gates a risky rollout or fault experiment.

**Contents:** [Evidence states](#evidence-states) · [Verification matrix](#verification-matrix) · [Test integrity](#test-integrity) · [Failure-path test catalogue](#failure-path-test-catalogue) · [Service objectives and operational ownership](#service-objectives-and-operational-ownership) · [Runtime signals that reveal amplification](#runtime-signals-that-reveal-amplification) · [Fault injection and chaos gates](#fault-injection-and-chaos-gates) · [Rollout and rollback contract](#rollout-and-rollback-contract) · [Migration execution](#migration-execution) · [Restore and failover evidence](#restore-and-failover-evidence) · [Evidence limitations](#evidence-limitations)

## Evidence states

Every verification claim carries one of the four states defined in the [core workflow](../SKILL.md):
`verified`, `reasoned_not_run`, `blocked`, or `not_applicable`. Confidence is not
evidence. A missing dependency makes a check `blocked`, never a pass. Never report a
command's output that was not produced.

## Verification matrix

Match rows to the failure surfaces the change actually has. Tier changes depth, not
applicability: pure computation has no network deadline to test, while consequential
arithmetic may need strong boundary/property tests without any distributed machinery.

| Failure surface | Minimum check | Tier 2/3 check | Runtime evidence |
|---|---|---|---|
| Local computation | Boundary values, units, rounding, overflow, empty input | Properties, numerical error budget, measured complexity | Precise error/result contract; telemetry only if useful |
| Collections / pagination | Empty, single-row, exact-page and page-plus-one sizes; invalid cursor | Tied sort keys, concurrent inserts/deletes/updates, resume and snapshot expiry | Duplicate/skip detection, rejected cursors, bounded page count |
| Type / module contract | Each reachable state and transition, rejected input classes, cleanup on every exit path | Exhaustiveness and type checks, sanitizers, deterministic interleavings across threads or awaits | Precise error/result contract; programmer errors fail loudly |
| UI / offline state | Stale completion, lifecycle cancellation, explicit accessible status | Interrupted sync, conflict/replay, persisted queue bounds | Pending age, sync/recovery state without sensitive content |
| Filesystem / device | Interrupted writes and owned-resource cleanup | Crash/power-loss or hardware tests against the platform contract | Recovery state and approved safety signals |
| Input boundary | Invalid, missing, oversized, deeply nested, high-cardinality | Property or fuzz corpus, adversarial payloads | Reject counts by bounded reason class |
| Security sink | Context-specific injection and canonicalization probes | Cross-boundary abuse cases from `secure-coding-overlay.md` | Denials and security findings by bounded class |
| Remote timeout | Forced slow dependency | Deadline propagation across the whole chain | Deadline-exceeded rate, dependency latency percentiles |
| Retry | Retryable and permanent failures | Retry storm against a degraded dependency | `retry_attempts / initial_attempts`, budget exhaustion |
| Idempotency | Repeat the same key | Timeout after a simulated commit, then replay the key | Dedup hits, conflicting key reuse, unresolved operations |
| DB concurrency | Parallel conflicting update; statement, lock-wait and idle-in-transaction limits | Serialization/deadlock retry of the full unit; cancellation and resource release | Conflict rate, serialization retries, pool/lock wait, idle transactions |
| Outbox | Rollback and commit both exercised | Crash between broker publish and mark-published | Oldest unpublished age, publish lag, duplicate publishes |
| Consumer / inbox | Same message delivered twice | Crash after DB commit, before broker ack | Redelivery rate, dedup rate, oldest message age |
| Poison handling | Permanently malformed message | Replay and quarantine procedure | Dead-letter depth, age, reason breakdown |
| Backpressure | Saturate the concurrency or queue cap | Slow dependency plus high ingress | Oldest useful work age, admission rejects, saturation |
| Policy limit | Limit reached and enforcement dependency unavailable | Concurrent/distributed reservation and reset behavior | Grants, denials, store failures, and budget remaining |
| Lease and fencing | Lease expiry | Pause the old holder, let a new holder acquire, resume the old one | Fence-reject count, lease renewal failures |
| Degradation | Dependency disabled | Several dependencies failing together | Degraded-response rate and duration |
| Auth and tenancy | Negative authorization matrix | Authz provider outage, adversarial tenant identifiers | Deny and fail-closed rate, cross-scope anomalies |
| Dependency/build integrity | Changed component identity and lock/provenance checks | Known-vulnerable or tampered fixture where supported | Scan findings, provenance failures, update age |
| Contract evolution | Old/new readers and writers against supported formats | Retained event replay and delayed mobile/offline clients | Compatibility rejects, unresolved operations, rollout version |
| Schema/backfill | Representative pre-migration data and restartable batches | Concurrent traffic, interrupted migration and rollback compatibility | Lock wait, replica lag, progress, invariant violations |
| LLM and tools | Invalid args, unauthorized tool, exceeded budget | Prompt injection via retrieved content, approval replay | Tool attempts, denials, approval failures, budget exhaustion |
| Cancellation | Cancel mid-operation | Worker killed during a durable transition | In-flight age, abandoned operations |
| Recovery | Restart or failover | Controlled fault plus restore drill | Time to safe steady state, reconciliation backlog |

Prefer deterministic clocks, injected randomness, controllable fakes, and
synchronization primitives over sleeps. A test that passes by timing luck is not
evidence.

## Test integrity

A test is evidence only if it can fail for the defect it guards.

- Watch a new regression test fail before the fix, or state that it was not observed failing.
- Assert the observable effect or the returned contract. A test that only asserts a mock was called proves the call, not the behavior.
- Fix the general case; production code has no branch that recognises test inputs.
- Before asserting current behavior, confirm it is the intended behavior. A test that pins a bug keeps it.
- Cover rejected and failing paths as well as the happy path: null, empty, negative and boundary inputs, and each error branch.
- For Tier 2/3 changes, prefer review by a fresh context that did not write the change, when the host provides one. The author's tests share the author's blind spots.

## Failure-path test catalogue

Select only the cases whose surface exists. A check that could not run is `blocked`,
never a pass.

- [ ] Success with representative input, and valid absence returning an explicit no-data result.
- [ ] Invalid, malformed, wrong-type, oversized, and excessively-nested input rejected with a stable error.
- [ ] Unauthenticated and unauthorized requests denied, including on cache-hit, fallback, and replay paths.
- [ ] Timeout on a dependency: expiry is correctly reported, cooperative completion is checked, and any required hard runtime bound is tested independently.
- [ ] Transient failure followed by success: retried and resolved within the attempt and deadline budget.
- [ ] Permanent failure: not retried, surfaced promptly.
- [ ] An effectful operation described as a read: not retried unless its semantics and effect certainty make repetition safe.
- [ ] Policy-enforcement dependency failure: authoritative security, abuse, cost, safety, or contractual limit remains enforced.
- [ ] Retry budget exhausted: the correct terminal result, known committed effects preserved, and partial or unknown effects explicitly reconciled rather than assumed rolled back.
- [ ] Duplicate request with the same idempotency key: one effect, consistent response.
- [ ] Same key with different request semantics: conflict, not a silent replay.
- [ ] Concurrent requests on the same key or resource: the invariant holds under real parallelism.
- [ ] Ambiguous write outcome (timeout after the effect committed): resolved without duplicating the effect.
- [ ] Crash or restart between claiming a key and committing: recovery leaves a consistent state.
- [ ] Partial multi-item result: per-item status returned, failed items reconciled or compensated.
- [ ] Fallback path exercised: security context preserved, result labelled degraded, not cached as ordinary success.
- [ ] Stale or degraded data blocked from driving a privileged or irreversible decision.
- [ ] Cancellation mid-flight: new work stops, cancellation propagates where supported, resources are released, and committed or unknown effects remain explicit.
- [ ] Graceful shutdown during in-flight work: drained or checkpointed, leases released.
- [ ] Worker lease expiry and redelivery: no duplicate effect, no lost message.
- [ ] Poison message: dead-lettered, pipeline continues.
- [ ] Retry exhaustion or quarantine retention reached: a durable obligation remains owned and recoverable, with controlled replay and unchanged operation identity.
- [ ] Bounds enforced: full queue, oversized payload, excessive fan-out, deep recursion, large result set.
- [ ] Backpressure: overload produces deliberate rejection or shedding rather than collapse.
- [ ] An expired attempt is stopped where the contract permits, while paid orders, reconciliation records and other durable obligations survive caller deadlines or lost worker leases.
- [ ] Stale lease holder resumes after a new holder acquired the lease: its write is rejected by fence.
- [ ] Cache failure: treated as a miss where safe, never as an authorization bypass.
- [ ] Logs and metrics from failure paths contain no secrets and no unbounded cardinality.
- [ ] Secret canaries, encoded payloads, and sink-specific injection probes do not reach telemetry, syntax, privilege, or unintended resources.
- [ ] Telemetry export fails or saturates: diagnostic buffering stays bounded, and any required durable audit follows its explicit failure policy.

## Service objectives and operational ownership

For a service or durable workflow, name the user journey and its accountable owner.
Define an SLI's good outcome, eligible population, measurement point and window before
choosing a target. Count user-visible timeout, loss, incorrectness and unacceptable
staleness according to that contract; an HTTP success or queue acknowledgement may only
prove acceptance. Measure completion or freshness separately for asynchronous work.
Document exclusions and missing-data behavior so apparent success cannot improve merely
because failed work stopped emitting metrics.

Agree the SLO and error-budget policy with the owner who can balance reliability and
feature work. Derive alerts from impact and budget consumption, including sustained
degradation; route urgent pages separately from planned work. Do not copy another
service's target, burn-rate threshold or release-freeze rule. Correctness, authority and
security invariants do not become optional when an availability budget remains.

Before handing over a material operational change, record:

| Responsibility | Minimum useful evidence |
|---|---|
| Response | Named team/role, alert route and escalation, bounded diagnostic steps, recovery action and access prerequisites |
| Capacity | Representative workload, peak and burst assumptions, dependency limits, headroom and cost envelope |
| Recovery | Stated recovery time and acceptable data loss, restore/reconciliation procedure, last exercise and remaining gaps |
| Upkeep | Owner and review date for temporary exceptions, feature flags, supported versions and deferred risks |

Use the existing operational system; do not create a new dashboard or on-call process
for a pure helper. For capacity tests, report offered load, achieved throughput,
latency distribution, failures and saturation together, including the load generator's
limits; a lower achieved request rate is not proof that overload was handled.

## Runtime signals that reveal amplification

Aggregate error rate hides the failures that matter most. Watch the signals that
show a system feeding its own failure:

| Signal | What it tells you |
|---|---|
| `retry_attempts / initial_attempts` | Retry amplification; spikes usually precede or deepen a dependency outage |
| Deadline-exceeded rate | Callers are no longer receiving useful work inside their budget |
| Dependency latency percentiles | Whether timeout budgets are tuned, or are themselves triggering retry storms |
| Admission reject / shed rate | Whether the system is protecting itself under excess demand |
| Policy-limit deny / enforcement-failure rate | Whether an authoritative budget is working, not whether capacity is saturated |
| Concurrent work and pool wait | Saturation, visible before outright errors |
| Oldest useful work age | Accepted work going stale even while depth looks healthy |
| Redelivery and dead-letter rate | Consumer failure and poison-message pressure |
| Oldest unpublished outbox age | Event propagation health |
| Dedup and key-conflict rate | Replay behavior and client misuse |
| Unknown-outcome backlog | Writes still awaiting reconciliation |
| Fence rejects | Stale owners actually attempting to write |
| Degraded-mode rate and duration | Availability preserved, at what fidelity cost |
| Tool denials and approval failures | Actions prevented by deterministic policy |
| Error-budget consumption | User-visible reliability, rather than raw component health |

Derive thresholds from this system's latency objective, capacity envelope,
usefulness deadline, and dependency contracts. Copying another system's timeout
and retry numbers is how retry storms are inherited.

## Fault injection and chaos gates

Progressive, not automatic:

- **Tier 0/1** — focused contract and boundary tests; deadline and cancellation tests only when those surfaces exist.
- **Tier 2** — add concurrency, duplicate, ambiguous-write, redelivery, overload, and dependency-fault tests in a controlled environment.
- **Tier 3** — add adversarial sink tests, negative authorization and tenancy tests, policy-dependency outage, secret canaries, and a production-like recovery drill.

Production chaos is optional and never a default. Run one only with all of:

- explicit authorization for this environment and fault experiment,
- a stated steady-state hypothesis with the metric that defines it,
- an explicitly bounded blast radius (which accounts, tenants, partitions, hosts),
- an automatic stop condition tied to that metric,
- a rollback and reconciliation procedure written before the experiment,
- an owner watching it in real time.

Test the recovery mechanism itself, not only the fault. Failover, replay,
restart, cache rebuild, and backlog drain are among the most common sources of
secondary incidents, because each adds work to a system already short of
capacity. Where the platform supports a dry run or preview of a recovery action,
use it before applying the action.

## Rollout and rollback contract

For any change that touches durable state, message formats, idempotency
records, policy, or agent tool schemas, answer these before shipping:

```text
deployment unit      What exactly is changing?
artifact and config  Which immutable build, configuration, flags and schema revision were verified?
owner and authority  Who may release, halt and recover it in this environment?
blast radius         Which users, tenants, regions, shared stores and downstream systems can be affected?
forward compatibility Can old and new versions run concurrently?
data compatibility    Is the migration expand/contract safe?
replay compatibility  Are in-flight messages and existing idempotency records still understood?
rollback              Can a binary or config rollback run safely against durable state the new version created?
irreversibility       Which effects cannot be rolled back and therefore need reconciliation?
canary                Which health, correctness, saturation, and security signals gate expansion?
stop condition        What halts the rollout, automatically or operationally?
postcondition         What evidence proves a safe steady state was reached?
```

A software rollback that cannot interpret durable work created by the new
version is not a rollback.

Compare a representative canary with a control using per-version signals, a meaningful
traffic sample and an explicit observation window. A green aggregate can hide a failed
small cohort. Account for delayed jobs, rare paths and shared-state effects: a database
migration can affect every instance even if the new binary receives little traffic.
State what missing telemetry does to promotion. Test the feature-disable path and give
temporary flags an owner and retirement condition; a flag does not undo committed data.

## Migration execution

Use [interface contracts](interface-contracts.md) for compatibility semantics. For a
durable change, build the actual old/new producer, consumer, client and stored-data
matrix, including supported offline clients and retained queue or quarantine messages.

1. Expand with a compatible additive change where possible. Inspect the engine/version's
   real locks, table rewrites, constraint validation and replication costs before applying
   it; additive syntax is not proof of an online migration.
2. Deploy readers and writers that tolerate the coexistence period. Identify the source
   of truth; temporary dual writes need failure handling and reconciliation, not an
   assumption that two independent writes are atomic.
3. Backfill in bounded, resumable, idempotent batches with a checkpoint and stop condition.
   Protect normal traffic, measure progress/lag, and define concurrent-write behavior.
4. Validate data and business invariants before switching reads or enforcing constraints.
   A successful migration command is not evidence that all existing data satisfies them.
5. Contract only after old binaries, supported clients and retained replays no longer
   require the old representation, and the rollback policy permits removal. Otherwise,
   keep compatibility or make a supported versioned break explicit.

Rehearse interruption and recovery against representative data. If reversal is unsafe,
prepare a tested forward repair or restore-and-reconcile procedure before release, and
identify the step after which a simple binary rollback stops being valid.

## Restore and failover evidence

Where durable data matters, define recovery time objective (RTO) and recovery point
objective (RPO) per critical data set or workflow, then test them. A successful backup
job or replica does not establish recoverability. Restore into an authorized isolated
environment and verify readable data, application invariants, required configuration,
keys, identities and dependencies. Measure the path to safe service, including restore,
replay and reconciliation, rather than only the file-copy duration.

Before reopening effects, address each applicable recovery boundary explicitly; matching
payment totals alone does not establish that the restored application is safe:

| Boundary | Evidence needed before reopening |
|---|---|
| External effects | Inventory completed payments, messages and object writes beyond the snapshot; reconcile missing deduplication records or prove repeat safety |
| Authority and privacy | Reapply required revocations/deletions and tombstones from authoritative surviving records; do not resurrect revoked access or data |
| Keys and configuration | Verify usable current credentials, necessary decryption keys, application/config/schema compatibility and dependency access |
| Ownership and capacity | Exclude stale writers and bound destination concurrency/backlog drain against actual capacity |
| Data and recovery objectives | Validate per-operation invariants, readable/complete data and measured time/loss through safe service |

Keep an unresolved boundary visible with its owner and next action. Mark a nonexistent
surface `not_applicable` with evidence; do not silently omit it or invent a pass. Test
backup access independently of a failed primary.

For failover, verify destination capacity, routing convergence, replica lag and acceptable
data loss. Prevent concurrent writers through the platform's actual quorum, fencing or
conditional-write guarantee; a routing switch alone is not ownership transfer. Exercise
failback and bounded backlog drain as well. Record the exact recovery point, measured
RTO/RPO, failures, owner and next exercise; where no safe drill ran, label the claim
`reasoned_not_run` or `blocked`.

## Evidence limitations

A passing unit or mock-transport test proves only the exercised behavior. It does not
prove real DNS, TLS, proxy, scheduling, hardware, crash-durability or provider behavior.
An async timeout uses cooperative scheduling and cannot preempt blocking native/CPU
work; test the completion boundary as well as the awaited timeout. Cancellation after
a commit must preserve the committed/unknown effect classification.

For a skill package, static metadata/link/corpus checks, executable example tests, and
model behavior evaluations are separate evidence classes. Record the skill revision,
model/host version, available tools, case-level results and failures before asserting
behavioral quality. A rubric or a synthetic fixture is not an executed model evaluation.
