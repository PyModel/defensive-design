# Defensive Design

[![verify](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml/badge.svg)](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml)

An architecture-neutral agent skill for **the smallest evidence-backed protection**
against failures that can violate a real contract. It works at every level, from a
single function or type to modules, applications and distributed systems. It adapts to libraries, CLIs, local
and mobile apps, services, streams, data pipelines, infrastructure, embedded components,
and agents without prescribing their implementation stack.

## Use and install

The skill itself is Markdown. It does **not** require Python, HTTPX, a database, a cloud,
or a particular agent provider. It uses the [Agent Skills format](https://agentskills.io/specification).
Format portability is not a claim that every host/model combination has been tested.

```bash
npx skills add PyModel/defensive-design
```

The installable package is [`skills/defensive-design/`](skills/defensive-design/). The
installer discovers it there and copies only that directory, so evaluation rubrics,
maintainer scripts, tests and work ledgers are never installed. Alternatively, copy
`skills/defensive-design/` into a skill directory your host supports, keeping `SKILL.md`,
`references/`, `assets/` and `LICENSE` together. The optional `agents/openai.yaml`
adapter is not required by the core workflow.
Verify the host's current installation and invocation conventions. To test an unmerged
change, use the exact review-branch checkout rather than assuming the default installer
selects that branch.

Example requests:

```text
Use $defensive-design to review this code. Report findings only; do not edit.
Use $defensive-design to design safe recovery without changing our architecture.
Use $defensive-design to implement this fix and its regression tests. Do not deploy.
```

Explicit invocation supports a minimal review even for pure helpers. Routine spelling,
renaming and trusted-fixture edits do not automatically warrant a defensive audit.
Consequence determines depth; a critical pure calculation does not thereby need retries.

## What changes in the workflow

| Decision | Behavior |
|---|---|
| Scope and evidence first | Distinguish review, design, implementation and incident work. Inspect contracts and code; report unknowns and conflicts instead of inventing repository facts. |
| Adapt before prescribing | Identify state ownership, authority, lifecycle, consequence and resource bounds. Reuse native facilities; justify every extra mechanism. |
| Preserve meaningful outcomes | Keep result, cause, effect certainty, policy and retry decisions separate. A timeout may follow a committed effect. |
| Bound recovery | Control retries, queues, stale work, fallback and reconciliation without causing secondary overload. |
| Respect execution semantics | Local locks may be correct; streams may be long-lived; cooperative cancellation is not CPU preemption; physical safe states follow approved hazard requirements. |
| Prove only what was checked | Record actual commands and scope. Package structure, HTTP example tests, model evaluations and production behavior are distinct evidence. |

## Package map

| Path | Purpose |
|---|---|
| [SKILL.md](skills/defensive-design/SKILL.md) | Concise workflow, trigger metadata, invariants and on-demand routing |
| [Code-level design](skills/defensive-design/references/code-level-design.md) | Invariant ownership by level, programmer versus input errors, boundary parsing, resource ownership, numbers/time/text |
| [Architecture adaptation](skills/defensive-design/references/architecture-adaptation.md) | Capability profile and context-specific decisions without a fixed architecture |
| [Assessment template](skills/defensive-design/assets/assessment-template.md) | Optional findings, implementation slices, evidence, migration and rollback record |
| [Failure taxonomy](skills/defensive-design/references/failure-taxonomy.md) | Multi-axis result/cause/effect model and repeat-safety decision |
| [Defensive checklists](skills/defensive-design/references/defensive-checklists.md) | Controls selected by actual failure surfaces |
| [Security overlay](skills/defensive-design/references/secure-coding-overlay.md) | Trust boundaries, sinks, authority, data and build security |
| [Verification and rollout](skills/defensive-design/references/verification-and-chaos.md) | Failure-path test catalogue, signals, permission-gated fault injection and recovery |
| [Primary sources](skills/defensive-design/references/sources.md) | Reviewed rationale and applicability limits |
| [HTTP example](skills/defensive-design/references/resilient_http_example.py) | Illustrative Python read-only client, not a mandatory dependency |
| [Evaluation guide](evals/README.md) | Maintainer-only: static checks versus actual agent behavioral evaluation (not installed) |
| [Maintenance guide](AGENTS.md) | Contribution, evidence and compatibility discipline |
| [Changelog](CHANGELOG.md) | Revision changes and migration notes |

## Maintainer verification

Only the executable example and package checks need Python 3.11+. Use a reviewed,
isolated environment and the [test requirements](requirements-dev.txt):

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python scripts/validate_skill.py
python scripts/verify_reference.py
python -m unittest discover -s tests -v
python scripts/mutation_check.py
python -m ruff check scripts skills tests
python -m mypy scripts tests
python -m mypy --strict skills/defensive-design/references
python -m compileall -q scripts skills tests
git diff --check
```

The package validator checks Agent Skills and documented host metadata rules, local
links (inline, reference-style and HTML), heading anchors, that every packaged file is
reachable from `SKILL.md`, the host adapter schema, and the evaluation corpus: matching
IDs, rubric polarity, duplicate prompts and a 20% negative-case floor. It uses safe
YAML with duplicate-key rejection and does not fetch links or execute examples from docs.
It is a project validator, not a complete Markdown parser or model evaluator.

The 56 HTTP reference checks cover bounded and slow-drip reads, per-attempt and
operation deadlines, retry classification and budgets, cancellation, breaker transitions,
input validation, JSON nesting and telemetry. `scripts/mutation_check.py` removes each
of 13 defensive controls in turn and fails if any removal goes undetected. Separate deterministic tests cover
late synchronous parsing/cleanup at the deadline and malformed package fixtures.
The reference rejects late completion but cannot preempt blocking CPU/native work.
DNS, TLS, proxies, real provider behavior and application-specific transport/logging
policies remain caller-owned integration boundaries.

CI preserves the required `Reference regression checks (3.11)` through `(3.14)` names,
uses a hash-locked test baseline, runs Ruff and mypy, and separately exercises minimum HTTPX 0.27.0 and a bounded
latest-0.x compatibility canary. Action revisions are pinned, token access is read-only,
credentials are not persisted, and job durations and artifact retention are bounded.
The source snapshot and environment artifact identify what actually ran. Pinning does
not constitute a supply-chain audit; operating-system runners remain managed images.

The corpus has **63 cases: 49 positive, 14 negative**, including Go, Rust, TypeScript, Java, C, Python and Kubernetes code-level cases. CI checks its structure, not agent
quality. See the evaluation guide for case-level behavioral testing before claiming
cross-model or cross-host support.

## Upgrade and rollback

Version 1.3.0 moves the installable package to `skills/defensive-design/`. The skill
name, the install command, and every path inside the package (`references/…`,
`assets/…`, `agents/…`) are unchanged; only repository-level paths gained the
`skills/defensive-design/` prefix. Manual installs should copy that directory. The
release also adds `references/code-level-design.md`, the `contract_violation` cause, a
surface-to-reference routing table, 15 evaluation cases (12 cross-language), and fixes to the
illustrative HTTP example (per-attempt total timeout, deadline-aware Retry-After, breaker
accounting, explicit JSON nesting bound, stricter header and text parsing). Run the
relevant host's trigger and behavior evaluations before broad adoption. No application
schema, infrastructure or data migration is introduced.

Rollback the package to the previous reviewed revision or revert the upgrade commits.
Version 1.2.0 remains a valid rollback target; reverting past 1.2.0 also restores the
known late-completion defect in the HTTP example.

## License

MIT. See [LICENSE](LICENSE).
