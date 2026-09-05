# Architecture Adaptation

Read this when the execution model is unfamiliar, spans several architectures, or is
not an always-online service. These are reasoning adapters, not mandatory components.
For a new architecture, derive controls from its capabilities and failure surfaces;
matching a row below is not required.

## Evidence profile

Capture what changes a decision, with path/symbol/revision or a declared assumption:

| Dimension | Questions |
|---|---|
| Contract | Who consumes the result? Which numerical, ordering, consistency, safety, accessibility, or compatibility properties matter? |
| Execution | Process, device, browser, thread, task, actor, interrupt, job, or distributed participant? Who starts and stops work? |
| State | Immutable, process-local, file, embedded store, shared database, remote resource? Who may mutate it and where is its commit point? |
| Authority | User capability, OS identity, device policy, server identity, signed artifact, or delegated agent scope? Where is enforcement authoritative? |
| Failure | Invalid data, numerical error, races, resource exhaustion, cancellation, power loss, disconnection, partial write, stale owner, or dependency fault? |
| Constraints | Supported versions, deployment form, offline requirements, latency/cost/resource budgets, organizational policy, and domain obligations? |
| Existing support | Which native abstractions already implement required validation, atomicity, recovery, and observation? What has actually been inspected? |
| Evidence gaps | Which files, environments, tests, operations, or dependencies are unavailable? What would resolve uncertainty? |

Do not infer a database from business terminology, distribution from asynchronous code,
or a security boundary from a directory name. A design document records intent; code,
configuration, tests, and runtime evidence can contradict it. Report that conflict.

## Select by failure surface

For each material risk, record the existing control, smallest missing protection,
verification, and any rejected complexity. A control is useful only where it covers
all participants in the invariant. Language and topology are implementation choices,
not substitutes for this proof.

| Context | Inspect and preserve | Proportional controls and checks | Do not assume |
|---|---|---|---|
| Pure library, numerical kernel | Value ranges, units, overflow, precision, aliasing, determinism, complexity, API contract | Native checked arithmetic/types where available, boundary/property tests, representative resource measurements | That pure means harmless; or that it needs retries, logging, a service, or a database |
| CLI, desktop, filesystem tool | Exit status, stdout/stderr contract, path authority, temporary files, interruption, atomic replace, permissions | Bounded parsing, safe arguments, scoped file access, cleanup and crash-recovery tests | An atomic rename alone proves power-loss durability; every platform has identical file semantics |
| Browser UI, native/mobile, offline app | Stale async responses, component lifecycle, optimistic state, offline queues, accessibility, device storage | Generation/cancellation guards, explicit pending/failed/partial states, bounded persisted operations and server reconciliation, accessible status updates | Hiding a button is authorization; client cancellation reverses a server commit; all state needs centralization |
| Single-process application or modular monolith | Shared memory ownership, module contracts, transaction boundaries, shutdown | Local locks/actors/immutable state where sufficient; store constraints for shared durable invariants | A distributed lock, message broker, service split, or network hop is needed |
| Network service or distributed system | Remote contracts, partitions, consistency, deadlines, duplicate effects, overload | Native deadlines/admission control, semantic retries, atomic idempotency or reconciliation, versioned contracts | Exactly-once external effects; unlimited fallback capacity; shared memory across replicas |
| Queue, stream, batch, ETL | Delivery/order guarantees, acknowledgment/checkpoint, poison records, backfill, late data | Bounded workers/batches and backlog age, replay-safe sinks, checkpoint/commit tests, poison isolation and monitored recovery | The stream must terminate; a producer outbox deduplicates a consumer; rerunning a batch is automatically safe |
| Embedded or real-time component | Scheduling, watchdogs, interrupts, device authority, memory bounds, power loss, approved hazard response | Platform-native resource/scheduling analysis, bounded critical work, device simulation and hardware tests as applicable | General-purpose async timeout proves a hard real-time deadline; an immediate shutdown is always safe |
| Infrastructure, configuration, deployment | Desired/actual state, drift, secrets, ordering, state ownership, mixed versions, blast radius | Native plan/preview and policy checks, staged changes, least privilege, rollback/restore proof | Application source alone describes deployed behavior; deployment permission follows from editing configuration |
| ML pipeline or agent orchestration | Input/model provenance, numerical quality, nondeterminism, schemas, tool authority, budgets, external effects | Versioned datasets/configs, reproducible evaluations, independent policy enforcement, bounded tools, exact-action approvals | A model judges its own permissions; a unit test proves task quality; free-text output is trusted code |
| Other or hybrid architecture | Its contract, ownership, authority, lifecycle, resource model, and material failure surfaces | Compose only justified controls and verify the seams between them | This table is exhaustive or a reason to force a redesign |

## Critical distinctions

**Security and physical safety:** fail closed for authority and security policy.
For physical processes, use the domain-approved safe-state and recovery requirements;
identify missing specialist/hardware evidence rather than improvising a hazard policy.
These are independent concerns and neither permits bypassing authorization.

**Local and global invariants:** a local lock can be exactly right for state owned by
one process. Global invariants need enforcement shared by all writers. Prefer an
existing transaction/constraint/conditional write to introducing distributed coordination.
If an external resource cannot reject stale owners, a lease alone is not a safety proof.

**Atomicity and durability:** a completed in-memory mutation, transactional commit,
filesystem rename, broker acknowledgment, and external side effect have different
failure boundaries. Verify the platform's actual crash and persistence guarantees.
Do not prescribe POSIX-only filesystem behavior to Windows or a remote object store.

**Deadline and cancellation:** synchronous work can exceed a cooperative deadline.
Check the clock at relevant completion boundaries and prevent stale output from taking
a new effect where possible. Hard runtime enforcement may need an isolated process,
platform limits, or real-time analysis. Never promise thread cancellation or rollback
of an effect that has already committed.

**Long-lived and unbounded:** a daemon or stream may intentionally run until canceled.
Bound active work, memory, queue age, idle waits where meaningful, and cleanup. Do not
add polling, artificial disconnections, or retries without a contractual need.

**Observability and privacy:** a small library may need precise returned errors and
tests, not a telemetry SDK. A UI needs understandable, accessible recovery states.
A production worker may need age/backlog and reconciliation signals. Choose useful,
bounded signals without leaking input, identity, prompts, tokens, or credentials.

## Migration and rollback

Keep public error/result types, resource identities, persisted formats and ownership
contracts stable unless the change explicitly requires evolution. For evolution, define
old/new producer and consumer compatibility, expand/contract phases, replay retention,
feature rollout gates, and rollback readability before removing old behavior.

An irreversible effect needs reconciliation, not a fictitious undo. A dependency upgrade
needs a reason, reviewed identity/version, tests, and a reversal plan. A skill-only
change does not migrate a user's application; do not generate application infrastructure
merely to demonstrate these principles.
