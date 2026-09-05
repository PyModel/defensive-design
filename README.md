# Defensive Design

[![verify](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml/badge.svg)](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml)

An architecture-neutral agent skill for **the smallest evidence-backed protection**
against failures that can violate a real contract. It adapts to libraries, CLIs, local
and mobile apps, services, streams, data pipelines, infrastructure, embedded components,
and agents without prescribing their implementation stack.

## Use and install

The skill itself is Markdown. It does **not** require Python, HTTPX, a database, a cloud,
or a particular agent provider. It uses the [Agent Skills format](https://agentskills.io/specification).
Format portability is not a claim that every host/model combination has been tested.

```bash
npx skills add PyModel/defensive-design
```

Alternatively, copy the whole `defensive-design` directory into a skill directory your
host supports. Keep `SKILL.md`, `references/`, `assets/` and evaluation links together.
The optional `agents/openai.yaml` adapter is not required by the core workflow.
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
| [SKILL.md](SKILL.md) | Concise workflow, trigger metadata, invariants and on-demand routing |
| [Architecture adaptation](references/architecture-adaptation.md) | Capability profile and context-specific decisions without a fixed architecture |
| [Assessment template](assets/assessment-template.md) | Optional findings, implementation slices, evidence, migration and rollback record |
| [Failure taxonomy](references/failure-taxonomy.md) | Multi-axis result/cause/effect model and repeat-safety decision |
| [Defensive checklists](references/defensive-checklists.md) | Controls selected by actual failure surfaces |
| [Security overlay](references/secure-coding-overlay.md) | Trust boundaries, sinks, authority, data and build security |
| [Verification and rollout](references/verification-and-chaos.md) | Tests, signals, permission-gated fault injection and recovery |
| [Primary sources](references/sources.md) | Reviewed rationale and applicability limits |
| [HTTP example](references/resilient_http_example.py) | Illustrative Python read-only client, not a mandatory dependency |
| [Evaluation guide](evals/README.md) | Static checks versus actual agent behavioral evaluation |
| [Maintenance guide](AGENTS.md) | Contribution, evidence and compatibility discipline |
| [Changelog](CHANGELOG.md) | Revision changes and migration notes |

## Maintainer verification

Only the executable example and package checks need Python 3.11+. Use a reviewed,
isolated environment and the [test requirements](requirements-dev.txt):

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_skill.py
python scripts/verify_reference.py
python -m unittest discover -s tests -v
python -m compileall -q scripts references tests
git diff --check
```

The package validator checks metadata, the repository's inline Markdown links/headings,
resource reachability, optional host metadata, and matching evaluation IDs. It uses safe
YAML with duplicate-key rejection and does not fetch links or execute examples from docs.
It is a project validator, not a complete Markdown parser or model evaluator.

The 43 original HTTP checks cover bounded reads, retry classification, cancellation,
breaker transitions, input validation and telemetry. Separate deterministic tests cover
late synchronous parsing/cleanup at the deadline and malformed package fixtures.
The reference rejects late completion but cannot preempt blocking CPU/native work.
DNS, TLS, proxies, real provider behavior and application-specific transport/logging
policies remain caller-owned integration boundaries.

CI preserves the required `Reference regression checks (3.11)` through `(3.14)` names,
uses a pinned test baseline, and separately exercises minimum HTTPX 0.27.0 and a bounded
latest-0.x compatibility canary. Action revisions are pinned, token access is read-only,
credentials are not persisted, and job durations and artifact retention are bounded.
The source snapshot and environment artifact identify what actually ran. Pinning does
not constitute a supply-chain audit; operating-system runners remain managed images.

The corpus has **48 cases: 40 positive, 8 negative**. CI checks its structure, not agent
quality. See the evaluation guide for case-level behavioral testing before claiming
cross-model or cross-host support.

## Upgrade and rollback

Version 1.2.0 preserves the skill name, existing reference paths and public HTTP result
types. Copy/update the complete package, not only `SKILL.md`, because new references are
loaded on demand. Run the relevant host's trigger and behavior evaluations before broad
adoption. No application schema, infrastructure or data migration is introduced.

Rollback the package to the previous reviewed revision or revert the upgrade commits.
That also restores the previous instructions and example behavior, including the known
late-completion defect; do not mistake rollback for a guarantee that prior behavior was
correct. Keep a verified bug fix when rolling back documentation independently.

## License

MIT. See [LICENSE](LICENSE).
