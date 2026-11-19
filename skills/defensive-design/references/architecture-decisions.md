# Architecture Decisions

Read this when a task changes component boundaries, dependencies, deployment topology,
state ownership, or a significant technology choice. Use it for an architectural
decision, not as a list of patterns to install. Apply the existing failure controls
through [architecture adaptation](architecture-adaptation.md).

**Contents:** [Start with measurable drivers](#start-with-measurable-drivers) · [Separate the design axes](#separate-the-design-axes) · [Compare viable options](#compare-viable-options) · [Enforce boundaries](#enforce-boundaries) · [Choose data and consistency deliberately](#choose-data-and-consistency-deliberately) · [Evolve without losing ownership](#evolve-without-losing-ownership) · [Record and revisit the decision](#record-and-revisit-the-decision) · [Primary anchors](#primary-anchors)

## Start with measurable drivers

Inspect the current system before proposing a target. Identify the business capability,
users, critical invariants, constraints, dependency graph, supported clients, and team
that will build and operate it. Include deployment frequency, support burden, skills,
total operating cost, vendor constraints, accessibility, and data obligations where
they affect the choice. A diagram of intended services is not evidence of isolation.

Turn the few most consequential quality goals into scenarios:

| Source and stimulus | Operating condition | Affected boundary | Required response | Measure and evidence |
|---|---|---|---|---|
| A client retries after losing a response | Dependency slow or unavailable | Order acceptance | Preserve one logical effect and expose a recoverable outcome | Duplicate-effect invariant, deadline and recovery target from the actual contract |
| A team changes one business rule | Old/new versions coexist | Owning module and public contract | Release safely without unrelated coordinated changes | Affected deployment units, compatibility checks and change lead time |

Replace illustrative measures with agreed targets or explicit unknowns. Do not invent
universal latency, availability, traffic, team-size, or cost thresholds. Rank conflicting
goals: stronger consistency, lower latency, independent deployment and lower operating
cost can trade against one another. Use a bounded experiment when a decision turns on
an unmeasured bottleneck; state the result that would change the recommendation.

Compare the current design, the smallest credible improvement, and alternatives that
meet the important scenarios. Record what each costs and which scenarios it cannot
satisfy. Preserve a working architecture unless evidence justifies changing it.

## Separate the design axes

Do not treat these as mutually exclusive choices:

- **Code organization:** cohesive modules, layers, vertical slices, ports/adapters,
  functional core and effectful shell. These govern dependencies and change locality.
- **Deployment and execution:** one process, separately deployed workers or services,
  serverless functions, actors, device/browser components. These govern lifecycle,
  scaling, failure and operational boundaries.
- **State and interaction:** transactions, request/response, messages, CQRS, event
  sourcing, caches and projections. These govern authority, consistency and recovery.

A modular monolith can use ports/adapters and asynchronous jobs. A microservice can be
layered or organized into vertical slices. CQRS does not require microservices, a
broker, separate databases, or event sourcing. A network boundary introduces failure
modes; it does not by itself create domain independence or a security boundary.

## Compare viable options

Use only rows relevant to the task. The catalog is deliberately non-exhaustive; derive
the same contract, cost and evidence for an unfamiliar style.

| Option | Consider when | Cost, rejection condition, and evidence needed |
|---|---|---|
| Cohesive modules in one deployment | Transactions and workflows are closely related; independent deployment is not a demonstrated need | Enforce module APIs and state ownership. Watch change coupling, resource contention and shared blast radius. Extract only when measured isolation, scaling or delivery needs outweigh distribution cost. |
| Layered or vertical-slice organization | Layers separate distinct policies; slices keep a use case's changes local | Choose dependency direction deliberately. Avoid pass-through layers, cyclic dependencies, a generic repository over every store, or duplicated security/invariant logic in each slice. Verify representative changes and boundary rules. |
| Ports/adapters, clean/onion boundaries | Domain rules need independence from volatile transports, frameworks or external providers | Keep business policy inside and technology translation at adapters. Add interfaces at meaningful seams, not one per class. Prove domain behavior without the external runtime, plus real adapter contract tests. |
| Independently deployed services | A capability has stable ownership and a concrete independent scaling, isolation or delivery requirement | Budget remote failures, version skew, observability, on-call ownership and cross-service data work. Reject a split that requires cross-service writes to the same owned tables or routine coordinated releases to function. Prove the proposed independence; sharing physical storage alone does not settle the ownership question. |
| Queue/worker or event-driven collaboration | Work can complete asynchronously, producers and consumers need temporal decoupling, or a fact has independent consumers | Define acceptance versus completion, event/command meaning, ordering scope, backlog limits and recovery owner. Queues buffer demand; they do not create processing capacity. Reject asynchronous semantics where the caller needs a synchronous invariant across participants. |
| CQRS and materialized read models | Read shape, performance or authorization needs materially differ from write invariants | Start with separate handlers/models over the same store if sufficient. Separate stores add synchronization and staleness costs; define read-your-write behavior and rebuild budget. Reject for uncomplicated CRUD without a demonstrated benefit. |
| Event sourcing | Durable event history is the authoritative domain record and replay/historical reconstruction is a real requirement | Design event evolution, concurrency, projections, replay side effects, retention/deletion and recovery before adopting. An audit log alone rarely justifies it. Limit scope; migration away is costly. Never replay external effects while rebuilding views. |
| Local transaction, outbox/inbox, or saga | A workflow crosses a real atomicity or ownership boundary | Prefer one native transaction when it covers the invariant. Use an outbox for a durable state change plus publication; consumers still handle duplicates. Use a saga only when intermediate states, compensations and reconciliation are acceptable. A saga does not provide global isolation or undo an irreversible effect. |
| Serverless or managed execution | Event-shaped or bursty work fits the provider's lifecycle and limits and reduces a demonstrated operations burden | Verify invocation/retry semantics, concurrency quotas, startup latency, time limits, network/identity boundaries, local-state lifetime and cost at expected load. Do not infer durable orchestration or exactly-once effects from the hosting label. |
| Pipeline, stream or batch stages | Work decomposes into stages with clear data contracts and independent throughput needs | Preserve ordering and checkpoint/commit semantics; bound buffers and fan-out, handle late data and schema changes, and measure the slowest stage. Reject extra stages that add serialization and operations without a useful boundary. |
| Plug-in or extension boundary | Trusted extensions need a stable capability interface, or third-party behavior must be isolated | Define extension versioning, allowed capabilities, resource/lifecycle limits and failure containment. An in-process interface is not a sandbox for untrusted code; use an appropriate isolation boundary when required. |

Pattern names do not prove security, maintainability, scalability, or readiness.
Use domain concepts to find cohesive boundaries, but do not turn every entity into a
service or require a full domain-modeling framework for simple CRUD. Share stable
invariants deliberately; do not force unrelated contexts to use one mutable model.

## Enforce boundaries

For each consequential component, establish:

| Contract | Required decision |
|---|---|
| Ownership | Who owns business rules, writes, lifecycle, failures and operational support? Which other writers exist? |
| Dependency direction | Which imports/calls are permitted? Which internal types and tables are private? Where do adapters translate external semantics? |
| Public interface | Inputs, outputs, units, errors, versions, authorization, resource limits, deadlines, cancellation and repeat safety |
| Durable behavior | State machine, atomic commit boundary, event/command identities, ordering, acknowledgment, retention and replay |
| Change and failure isolation | What can release or fail independently? What shared database, identity provider, queue, host or control plane still couples it? |

Make the important boundaries executable with existing facilities: package visibility,
module dependency rules, import checks, database roles, contract tests, or integration
tests. Choose checks for the invariants actually at risk. A folder convention without
enforcement is an intention, not a guarantee.

Use cohesion, composition and SOLID as questions about actual change and correctness:
does one module own a coherent responsibility; can a replacement preserve its caller's
preconditions, outcomes and invariants; do clients depend only on capabilities they
use; and can volatile details change without rewriting stable policy? Prefer
composition when it avoids inheritance coupling, but preserve sound substitutable
types. Do not convert these principles into interface-per-class rules, speculative
extension frameworks, or abstractions that hide transactions and errors.

Choose API or messaging technology from interoperability, client support, evolution,
latency and streaming needs; REST, RPC, GraphQL and events each retain their own
validation, authorization and resource limits. A gateway or client-side schema does
not remove enforcement at the operation that owns the effect.

## Choose data and consistency deliberately

Name the authoritative source for each fact. A cache, search index, read replica,
analytics table or vector index is derived unless the design explicitly gives it
authority. Define its freshness requirement, rebuild path, and behavior during drift.

- Choose a store from access patterns, transactions and constraints, expected data
  size and growth, query/index needs, retention, backup/restore, operational skill,
  and cost. Prefer an existing adequate store to unnecessary polyglot persistence.
- Specify consistency for the operation: uniqueness, conservation, ordering,
  read-your-write, monotonic reads, or a measured staleness bound. State behavior during
  partitions, replication lag and failover. Do not reduce the decision to a vague
  "SQL versus NoSQL" or "choose two" slogan.
- Choose partition and tenancy boundaries from hot-key/skew risk, cross-partition
  transactions, isolation, data placement and growth. Validate realistic distributions,
  not only evenly distributed synthetic traffic.
- Separate business identity from storage layout; preserve units, precision, uniqueness
  and allowed state transitions through constraints owned by the authoritative writer.
- Justify replication and multi-region writes against actual recovery/latency goals.
  Define conflict ownership and stale-writer prevention before claiming active-active
  safety. Replication is not a substitute for a recoverable backup.

Use [defensive checklists](defensive-checklists.md) for transaction, idempotency,
messaging, cache and concurrency details; use [verification and rollout](verification-and-chaos.md)
for recovery evidence. Keep mechanism details out of the architecture decision unless
they determine whether its invariants are achievable.

## Evolve without losing ownership

Prefer reversible slices with explicit cutover criteria:

1. Establish the existing contract and baseline. Name the future state owner and
   every reader/writer affected, including jobs, administration and old clients.
2. Introduce a seam and enforce dependencies before moving deployment boundaries.
   Use an adapter/anti-corruption layer when external semantics must not leak inward.
3. Expand contracts for mixed versions. Backfill/checkpoint data with bounded work,
   repeat safety and reconciliation; test representative old and new clients.
4. Compare behavior using safe shadow reads or replay without external effects.
   Do not create two independent authoritative writers as a migration shortcut.
5. Cut over in bounded increments with observability and stop conditions. Specify
   how rollback reads newly written state or when only forward repair is safe.
6. Remove the old route, writes and schemas only after evidence that no supported
   consumer or in-flight work depends on them. Retire temporary adapters and flags.

For a service extraction, transfer data and operational ownership together. For a
consolidation, remove obsolete remote hops and duplicate state owners deliberately.
Do not mistake deployment completion for migration completion or recovery readiness.

## Record and revisit the decision

Use a short architecture decision record for consequential or costly-to-reverse
choices; ordinary local changes need only a concise rationale. Follow the repository's
existing format. Include:

- Context, inspected evidence, assumptions and ranked quality scenarios.
- Considered options, chosen option, rejected alternatives and explicit non-goals.
- Ownership, dependencies, invariants, affected contracts and blast radius.
- Consequences: complexity, cost, latency, security, operability and team obligations.
- Verification, migration/recovery plan, accountable owner and unresolved evidence.
- Status and a concrete revisit trigger, such as an observed capacity limit, support
  burden, change-coupling problem or changed requirement. Unknown thresholds stay open.

Keep accepted decisions traceable when superseded. Measure whether the promised
outcome occurred, and remove a mechanism that no longer earns its operating cost.
Do not require standing committees or new paperwork for reversible local work.

## Primary anchors

These sources inform the choices; the tables above are project synthesis, not a
requirement to adopt a vendor or claim conformance.

- [SEI Quality Attribute Workshop](https://www.sei.cmu.edu/library/quality-attribute-workshop-collection/): prioritize and refine business-driven quality scenarios.
- [Cockburn's ports/adapters article](https://alistair.cockburn.us/hexagonal-architecture): isolate application policy from external adapters and test it independently.
- [Azure architecture styles](https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/): compare structural choices and their constraints.
- [Azure CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs): separate read/write models proportionally; messaging and event sourcing are optional.
- [Azure event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing): weigh historical reconstruction against schema, concurrency, replay and migration costs.
- [AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html): close the state/publication dual-write gap and account for duplicate delivery.
- [AWS saga orchestration](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html): evaluate compensation, idempotency and the absence of global transaction isolation.
- [AWS ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html): preserve context, decisions, consequences and supersession.
