# Interface and Data Contracts

Read this when a change crosses a module, API, event, cache, client, or durable-data
boundary. Define the observable contract before choosing REST, RPC, GraphQL, messaging,
schema tooling, or generated clients. Reuse the repository's conventions.

**Contents:** [Name the contract and its owner](#name-the-contract-and-its-owner) · [Preserve command and result semantics](#preserve-command-and-result-semantics) · [Represent asynchronous work honestly](#represent-asynchronous-work-honestly) · [Evolve schemas across real consumers](#evolve-schemas-across-real-consumers) · [Make event contracts replayable](#make-event-contracts-replayable) · [Treat caches as derived state](#treat-caches-as-derived-state) · [Keep client state and durable effects separate](#keep-client-state-and-durable-effects-separate) · [Verify the boundary](#verify-the-boundary)

## Name the contract and its owner

For each changed boundary, record only material fields:

| Question | Required decision |
|---|---|
| Who owns the fact? | Authoritative component/store, allowed writers, derived copies |
| Who may act or read? | Principal, tenant, object, field and operation scope; enforcement boundary |
| What is accepted? | Types, optional versus null, units, precision, encoding, bounds and semantic invariants |
| What can the caller observe? | Success, absence, conflict, partial result, rejection, cancellation and uncertain effect |
| What is promised over time? | Consistency, freshness, ordering, expiry, repeat safety and supported versions |
| What can this consume? | Payload/result size, page size, query complexity, fan-out, duration and concurrency |
| Who maintains it? | Owning team/module, compatibility tests, deprecation policy and recovery responsibility |

Validate syntax and semantics at the relevant boundary; static types and generated
clients do not establish runtime validity or authorization. Define unknown-field policy
by direction: an extensible response can tolerate unknown non-critical fields, while a
write must never mass-assign unrecognized or protected fields. Define how missing,
explicitly null, empty, zero and default values differ. Use an explicit patch contract.

## Preserve command and result semantics

- Give commands stable business intent and distinguish acceptance from completion.
  Keep the [failure taxonomy](failure-taxonomy.md) through adapters and gateways.
- Bind repeatable writes to a scoped identity and canonical request. Reject reuse for
  different intent; serialize concurrent duplicates and define pending, completed,
  expired and unknown states. An idempotency record needs retention consistent with
  the client's retry/replay window. Short deduplication TTLs must not permit an old
  payment or destructive request to become a new effect.
- Prevent lost updates with an atomic expected-version write where the contract needs
  it. HTTP `If-Match` uses strong entity-tag comparison; comparing in application memory
  and then saving unconditionally leaves the race. Version checks and idempotency
  solve different problems and do not replace each other.
- Define atomic versus partial bulk semantics. Return stable item identities and
  recoverable per-item outcomes without leaking unauthorized existence. Retrying the
  whole batch must not duplicate successful items. Bound batch size and work.
- Bound filtering, sorting, pagination and expensive traversals. Validate cursor scope,
  ordering and version; describe snapshot or live-view semantics. A page token is not
  authority. See [code-level design](code-level-design.md) for mutable-list traversal.
- Keep public failures stable and actionable. Preserve causes internally; return no
  stack traces, credentials, sensitive payloads or raw dependency messages.

## Represent asynchronous work honestly

When completion outlasts the request, choose a durable acceptance mechanism only if the
business obligation must survive the process. A `202` response is acceptance, not a
successful completed effect; do not acknowledge durable work before recording it.

Define a stable operation identity, authorized status/result lookup, permitted state
transitions, polling/backoff or notification policy, retention and terminal outcomes.
Return the same operation for a safe duplicate submission. Keep polling load bounded.
Protect status and result resources with the same tenant and object permissions as
submission; a hard-to-guess identifier alone is not authorization.

Separate cancellation requested, execution stopped, compensation needed and effect
committed. A disconnected caller or expired worker lease does not erase accepted
obligations. Preserve unresolved effects for an authorized recovery owner; expose a
pending/unknown state until authoritative evidence resolves it.

## Evolve schemas across real consumers

Check compatibility in both directions: old writer to new reader and new writer to old
reader, including persisted records, queued events, generated clients and delayed mobile
updates. A new field or enum member is not automatically safe: strict deserializers,
exhaustive switches, numeric conversions, defaults and validation rules can change
behavior even when the wire format still parses.

Preserve meaning, units, identity, authorization and failure semantics as well as field
names. Define unknown enum handling explicitly; unknown financial/security states must
not become success or allow. Do not reinterpret an existing field or reuse a retired
schema tag for different data. Follow the actual serializer's compatibility rules.

Record supported versions and real retirement evidence. Use adapters, explicit versions
or capability negotiation where required; a version number alone supplies no migration.
Keep public contracts independent of internal database entities. Use the
[verification and rollout guide](verification-and-chaos.md) for deployment order,
backfills, contraction gates and recovery against new durable state.

## Make event contracts replayable

Specify event type/schema version, producer identity, stable event identity, aggregate
identity/version where ordering matters, occurrence time and permitted payload scope.
Distinguish a past fact from a command requesting an action. Do not embed credentials or
unnecessary personal data into long-retained events.

Define deduplication scope, retention, ordering/partition assumptions and the source of
truth for missed or out-of-order events. A unique event ID does not deduplicate two
different events that request the same business effect; enforce that invariant too.
Timestamps alone do not prove causal order across hosts.

State what replay may change. Projection rebuilds must not resend emails, charge money
or resurrect deleted records merely because historical events are read again. Gate
external effects with durable identities or a replay mode that suppresses them; test
crash/restart boundaries. Outbox/inbox mechanics belong in
[defensive checklists](defensive-checklists.md), not in an exactly-once assertion.

## Treat caches as derived state

Declare the authoritative value, allowed staleness and invalidation/rebuild owner. Key
every correctness-relevant dimension, including tenant, authorization scope, locale and
schema/version as applicable. Authorize cache hits; define shared-cache and browser/CDN
behavior for sensitive responses. Keep absence, permission denial and dependency error
distinct when considering negative caching.

Test the race where an old read refills the cache after a newer write invalidates it.
Choose versioned values, conditional updates, invalidation ordering or an explicit
bounded-staleness contract. A TTL bounds some stale values; it does not itself preserve
a strong consistency or revocation guarantee. Bound entry size/count, stampedes and
rebuild work, including the load transferred to the origin during cache failure.

## Keep client state and durable effects separate

Represent loading, empty, denied, unavailable, pending, partial, stale and completed
states as required by the interface. Keep status changes accessible and give the user a
recovery action. A spinner ending or a button disabling does not prove server completion
or prevent duplicate requests from another tab/device.

Use lifecycle/generation protection so an old response cannot overwrite a newer screen.
After reconnect, reconcile with authoritative operation state before retrying an
uncertain mutation. For offline queues, bind each intent to its actor/tenant, stable
identity, schema version and expected resource version; define conflicts, expiry and
account-switch cleanup. Never replay one user's queued action as another user.

Preserve local evidence if a storage write fails; do not report a successful durable
save or silently restore already completed actions. Treat notification delivery as a
hint to refresh state, unless its own authenticated contract provides stronger evidence.

## Verify the boundary

Use consumer/provider contract tests when independently evolving clients warrant them.
Test supported old/new schemas, unknown values, null/missing/default distinctions,
cross-tenant access, concurrent duplicates, stale-version updates, partial batches,
lost responses, replay after retention boundaries and client reconnect/account switch.
Check observable state and effects; a mock invocation or schema snapshot alone does not
prove the business invariant. Use real persistence/integration tests for guarantees
that depend on transactions, serializer versions or cache behavior.

Primary anchors: [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html),
[API implementation](https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-implementation),
and [asynchronous request-reply](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply).
The cross-platform decision questions are this project's synthesis; these sources do
not require adopting HTTP, Azure, a broker or a new schema framework.
