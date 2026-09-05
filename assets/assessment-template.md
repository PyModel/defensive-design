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

## Findings and decisions

| ID / severity / evidence state | Location and trigger | Invariant and impact | Existing control | Minimal change or explicit non-applicability | Verification |
|---|---|---|---|---|---|

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

## Final status

Separate fixed and verified, implemented but unverified, open findings, and blockers.
Report branch/commit/PR/deployment state separately. Do not treat an authored test,
static analysis, or this completed template as an executed behavioral test.
