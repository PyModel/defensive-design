# Defensive assessment

Use only the sections material to this task. Fill them with actual evidence; this is
an optional output aid, not an executable configuration or mandatory reporting format.

## Scope and contract

- Mode and authorized actions:
- Inspected revision, paths, symbols, and runtime/configuration evidence:
- Exclusions, conflicting evidence, and unknowns:
- Observable acceptance criteria and critical invariants:
- Execution model, state ownership, authority boundary, lifecycle, and budgets:
- Consequence tier and relevant failure surfaces:

## Architecture and delivery decision

Use for a significant design/change; a small fix can answer these in a few sentences.

- Assumptions, material unknowns, evidence that would change the decision:
- Quality scenarios: workload/failure, required response, measurable acceptance target:
- Existing design, simpler alternative, chosen boundaries and rejected alternatives:
- Authoritative state, dependency direction, API/event/schema and consistency contracts:
- Tradeoffs: correctness, latency, capacity, security, maintainability, cost and team ownership:
- Blast radius: users/tenants, dependencies, data, privileges and failure domains:
- Delivery owner, ordered slices, migration dependencies and review/revisit trigger:

## Findings and decisions

| ID / severity / evidence state | Location and trigger | Invariant and impact | Existing control | Minimal change or explicit non-applicability | Verification |
|---|---|---|---|---|---|

Severity is the consequence if triggered; state likelihood separately.

- **Critical:** authority, safety, irreversible loss or cross-tenant exposure. Blocks release.
- **High:** wrong result or durable inconsistency on a plausible trigger.
- **Medium:** degraded behavior with a bounded, recoverable effect.
- **Low:** hardening or clarity; no current contract violation.

Describe rejected alternatives and why they add cost without preserving an additional
needed invariant. Keep confidence separate from executed evidence.

## Implementation slices

| Slice | Dependencies and scope | Acceptance criteria | Tests | Observable result | Migration and rollback |
|---|---|---|---|---|---|

## Verification and rollout

| Command or inspection | Revision and environment | Result and evidence state | Limitation / next action |
|---|---|---|---|

State compatibility with old/new readers, writers and in-flight work; rollout owner and
stop condition; irreversible effects and reconciliation; and the postcondition proving
safe recovery. For local/no-deployment changes, explain why those controls do not apply.

| Readiness question | Evidence or gap | Owner / next action |
|---|---|---|
| Applicable contract, edge/failure paths and negative authorization verified? | | |
| Recovery bounded; ambiguous effects and durable obligations preserved? | | |
| Mixed-version clients/data/replay compatible; rollback or forward repair safe? | | |
| User-facing signals, alert/runbook, capacity/cost and operator ownership defined? | | |
| Restore/failover and key/data retention meet stated recovery objectives? | | |
| Remaining risks explicit, with stop conditions and no unsupported readiness claim? | | |

Use `not_applicable` with a reason for nonexistent surfaces. An accepted risk needs the
appropriate decision owner; this template cannot accept a critical risk on their behalf.

## Final status

Separate fixed and verified, implemented but unverified, open findings, and blockers.
Report branch/commit/PR/deployment state separately. Do not treat an authored test,
static analysis, or this completed template as an executed behavioral test.
