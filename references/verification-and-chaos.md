# Verification, Signals, and Rollout

Companion to `SKILL.md`. Use for Tier 2 and Tier 3 work: what to test, what to
watch at runtime, and what gates a risky rollout or fault experiment.

## Evidence states

Every verification claim carries one:

| State | Meaning |
|---|---|
| `verified` | The check was actually executed, or authoritative runtime output was inspected |
| `reasoned_not_run` | The behavior follows from code inspection; nothing was executed |
| `blocked` | Verification was appropriate but unavailable — no environment, credentials, data, or tooling |
| `not_applicable` | The failure surface or control does not exist in this design |

Confidence is not evidence. A missing dependency makes a check `blocked`, never
a pass. Never report a command's output that was not produced.

## Verification matrix

Match rows to the failure surfaces the change actually has. Tier changes depth, not
applicability: pure computation has no network deadline to test, while consequential
arithmetic may need strong boundary/property tests without any distributed machinery.

| Failure surface | Minimum check | Tier 2/3 check | Runtime evidence |
|---|---|---|---|
| Local computation | Boundary values, units, rounding, overflow, empty input | Properties, numerical error budget, measured complexity | Precise error/result contract; telemetry only if useful |
| UI / offline state | Stale completion, lifecycle cancellation, explicit accessible status | Interrupted sync, conflict/replay, persisted queue bounds | Pending age, sync/recovery state without sensitive content |
| Filesystem / device | Interrupted writes and owned-resource cleanup | Crash/power-loss or hardware tests against the platform contract | Recovery state and approved safety signals |
| Input boundary | Invalid, missing, oversized, deeply nested, high-cardinality | Property or fuzz corpus, adversarial payloads | Reject counts by bounded reason class |
| Security sink | Context-specific injection and canonicalization probes | Cross-boundary abuse cases from `secure-coding-overlay.md` | Denials and security findings by bounded class |
| Remote timeout | Forced slow dependency | Deadline propagation across the whole chain | Deadline-exceeded rate, dependency latency percentiles |
| Retry | Retryable and permanent failures | Retry storm against a degraded dependency | `retry_attempts / initial_attempts`, budget exhaustion |
| Idempotency | Repeat the same key | Timeout after a simulated commit, then replay the key | Dedup hits, conflicting key reuse, unresolved operations |
| DB concurrency | Parallel conflicting update | Serialization failure and deadlock paths | Conflict rate, serialization retries, pool wait |
| Outbox | Rollback and commit both exercised | Crash between broker publish and mark-published | Oldest unpublished age, publish lag, duplicate publishes |
| Consumer / inbox | Same message delivered twice | Crash after DB commit, before broker ack | Redelivery rate, dedup rate, oldest message age |
| Poison handling | Permanently malformed message | Replay and quarantine procedure | Dead-letter depth, age, reason breakdown |
| Backpressure | Saturate the concurrency or queue cap | Slow dependency plus high ingress | Oldest useful work age, admission rejects, saturation |
| Policy limit | Limit reached and enforcement dependency unavailable | Concurrent/distributed reservation and reset behavior | Grants, denials, store failures, and budget remaining |
| Lease and fencing | Lease expiry | Pause the old holder, let a new holder acquire, resume the old one | Fence-reject count, lease renewal failures |
| Degradation | Dependency disabled | Several dependencies failing together | Degraded-response rate and duration |
| Auth and tenancy | Negative authorization matrix | Authz provider outage, adversarial tenant identifiers | Deny and fail-closed rate, cross-scope anomalies |
| Dependency/build integrity | Changed component identity and lock/provenance checks | Known-vulnerable or tampered fixture where supported | Scan findings, provenance failures, update age |
| LLM and tools | Invalid args, unauthorized tool, exceeded budget | Prompt injection via retrieved content, approval replay | Tool attempts, denials, approval failures, budget exhaustion |
| Cancellation | Cancel mid-operation | Worker killed during a durable transition | In-flight age, abandoned operations |
| Recovery | Restart or failover | Controlled fault plus restore drill | Time to safe steady state, reconciliation backlog |

Prefer deterministic clocks, injected randomness, controllable fakes, and
synchronization primitives over sleeps. A test that passes by timing luck is not
evidence.

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
