# Defensive Design 1.3.0 work ledger

## Scope

User request (2026-09-22): full critique plus architecture improvement, generalize to any
code at any level, validate every coding reference against live sources, and apply the
architecture candidates. Branch `improve/generalized-code-level-design` from `main@3fd605e`.
No commit, push, release, deployment or host-wide installation was authorized.

## Completed

- [x] Critique of the whole package plus an independent code/CI audit. The audit found
  0 P0/P1, 6 P2 and 15 P3 findings and 12 validator gaps. All are fixed except the
  open items listed under Remaining.
- [x] Code-level design reference, `contract_violation` cause, surface routing table.
- [x] External links: all 31 checked return HTTP 200; OWASP ASVS (404) and the moved
  OpenAI skills page were replaced. Language claims were checked against Python, Java,
  C, .NET, Rust, Go, MDN and TypeScript documentation; the HTTPX TLS/connect claim was
  checked against httpcore source.
- [x] Layout: package moved to `skills/defensive-design/`. The decision was based on the
  `skills` CLI source (commit 7407f38): its copy exclusions and its `skills/` discovery.
  Jev `decide` p=0.99. Splitting the checklist was rejected (Jev p=0.97): it would exceed
  the SKILL.md budget, create nested references and break a documented path.
- [x] HTTP example fixes F1-F3, F8, F11-F17, with a regression for each.
  `scripts/mutation_check.py` kills all 13 targeted mutants and runs in CI.
- [x] Validator gaps V1-V11, the V12 license-copy check, the F7 folder-name half, F21,
  and local-link checks for repository docs; 44 validator tests.
- [x] CI: hash-locked universal baseline, Ruff and mypy, an empty-tree whitespace check,
  and main runs no longer cancelled. Check names are unchanged.
- [x] Evals: 63 cases (49 positive, 14 negative), rubric polarity normalized.

## Remaining (explicit, not silently deferred)

- `not_applicable`, V12 nesting-depth rule: the direct-link rule (every file under
  `references/` or `assets/` is linked from `SKILL.md`) already enforces one level
  deep.
- Open, V12 token estimate: the 16 KiB byte budget stands in for a token count. A real
  estimate needs a host-specific tokenizer, which would be a new dependency, so it was
  not added.
- Open, F7 import half: tests import `scripts.*` only when run from the repository root
  (the documented command). Other working directories are unsupported and have no
  bootstrap.

## Verification evidence

`verified` locally, 2026-09-22. Each interpreter used its own venv built from
`pip install --require-hashes -r requirements-dev.txt`: Python 3.11.14, 3.12.0,
3.13.11 and 3.14.7. On all four, the following passed: `validate_skill.py`,
`verify_reference.py` (56 checks), unittest (48 tests), `mutation_check.py` (13/13
killed), Ruff, mypy, strict mypy on the example, compileall, and `pip check`. The HTTPX
0.27.0 compatibility run passed on 3.11. An empty-tree `git diff --check` passed, and
all 31 external links returned 200.

`jev_gate` escalated twice. The first gate verified 7/7 fix claims, with patch review
safe_to_apply 0.57. The second contradicted an incomplete compatibility claim, which is
now corrected in CHANGELOG, and scored safe_to_apply 0.61. The review score stayed
below the auto threshold (0.8).


The local results live in the final report. The hosted CI result belongs in the PR
record once the branch is pushed; it is not claimed here.

- `verified` sample behavior: one fresh Claude Opus subagent (this host, 2026-09-22)
  ran cases 50, 51, 54, 55 and 59 without access to `evals/`. It matched all 5
  rubric rows. This is a 5-case sample, not a corpus pass.
- `blocked`: full 63-case corpus runs across hosts and models.
- `verified` installer behavior: `npx skills@latest add <repo> --list` found exactly one
  skill. A real global install into a throwaway HOME (`-a claude-code`) copied only the
  12 package files, with no `evals/`, `tests/`, `tasks/` or CI.
- `reasoned_not_run`: other hosts' manual copy conventions.

## Rollback

Revert the branch commits or reinstall the 1.2.0 package. Package-relative paths are
unchanged, so installed copies need no migration.

---

## Historical 1.2.0 record (not current task instructions or new evidence)

### Defensive Design 1.2.0 work ledger

## Scope

User-authorized review, generalized improvements, tests and push to a review branch.
Baseline: `109c36dfe9a8202d93bdd64275d8936951d941d7`.
Branch: `improve/universal-defensive-design`; PR #3. Main remains protected and unmerged.
No production deployment, application migration, release tag or host-wide installation.

## Completed implementation and acceptance checks

- [x] Inspect the package, reference implementation, existing tests, evaluation corpus,
  workflow and branch protection; preserve the proven core and existing public paths.
- [x] Reproduce late synchronous parsing/cleanup returning HTTP success after expiry.
  Three new cases failed before the repair; all four deadline cases pass after it.
- [x] Repair completion-time classification without claiming CPU preemption or changing
  public result types. Correct the nested-retry count comment to include the initial attempt.
- [x] Generalize the core by state ownership, authority, lifecycle and consequence; add
  optional architecture and assessment references with explicit migration/rollback.
- [x] Correct over-broad pure-helper, local-lock and all-tiers timeout guidance; preserve
  fail-closed security and domain-approved physical safe-state requirements.
- [x] Preserve 32 original trigger cases and add 16 cross-architecture cases, paired with
  outcome-based rubrics. Maintain positive and negative selection coverage.
- [x] Add offline package validation and negative tests for YAML, links, scope escapes,
  metadata, resource reachability, corpus integrity and host invocation metadata.
- [x] Harden CI pins, permissions, budgets and evidence artifacts; retain all four
  required check names and separate pinned-baseline tests from compatibility canaries.
- [x] Document maintenance, installation compatibility, upgrade and rollback limitations.

## Current verification evidence

`verified` locally with Python 3.13.5, HTTPX 0.28.1 and PyYAML 6.0.3:

| Command | Outcome and scope |
|---|---|
| `python scripts/validate_skill.py` | Package metadata, local inline links/headings, resource links and exact eval/rubric structure pass. |
| `python scripts/verify_reference.py` | All 43 original HTTP reference checks pass. |
| `python -m unittest discover -s tests -v` | 34 tests pass: four deadline regressions and 30 validator tests. |
| `python -O -m unittest discover -s tests -p test_validate_skill.py -v` | All 30 validator tests also pass with assertions disabled. |
| `python -m compileall -q scripts references tests` | Python syntax compilation passes. |
| `git diff --check` | No whitespace errors in the current diff. |

`verified` hosted execution for the isolated runtime fix `1d27af1`:
GitHub Actions run `33936328372` completed successfully across Python 3.11-3.14,
including the 43 original checks and four new deadline regressions. The final package
workflow is additionally checked on the PR's final head; its outcome belongs in the PR
checks and review record, not an invented advance pass in this ledger.

The initial workflow-hardening run `33935477515` also passed, and its checked-source
artifact supplied an exact local copy for inspection. Git blob identity is used to
compare local tested files with the pushed package.

## Remaining verification boundaries

- `blocked`: independent host/model behavioral evaluation was not executed in this
  maintenance run. The 48 cases are an authored corpus, not 48 successful model runs.
  Run them with recorded host/model/tool versions before claiming cross-host quality.
- `blocked`: Ruff and mypy were not installed in the local environment. No current
  lint/type-check pass is claimed; syntax and executable regressions were run.
- `not_applicable`: application schema/infrastructure migration and production chaos.
  This change is a skill package and optional HTTP example, not an application rollout.
- `reasoned_not_run`: DNS, TLS, proxies, actual providers, hardware timing, physical
  safety and application-specific access logs require their owning integration tests.
- Generalized instructions do not prove robustness for every possible codebase.

## Rollout and rollback

Review the separate CI, runtime, core-guidance, evaluation and package-validation commits.
Require the final PR checks to pass; do not bypass main protection. Install the whole
package from the reviewed revision. Gate wider host adoption on behavioral evaluation.
Rollback the relevant commits/package revision; avoid reintroducing the known deadline
bug when reverting only instructional changes. No durable application data is changed.

---

## Historical 1.1.0 record (not current task instructions or new evidence)

The following record predates this upgrade. Its previous no-push scope, environment,
independent-review and verification statements are historical, not claims re-executed
or instructions governing the user-authorized 1.2.0 maintenance task.

# Defensive Design Skill Enhancement

## Plan

- [x] Add failing regressions for the known reference defects; preserve passing terminal-state and cancellation coverage.
  - Acceptance: `.` and `..` are rejected before I/O; unpaired surrogates become plain validation errors; control characters cannot enter logged correlation IDs; malformed encoding, `501`, `505`, and local pool saturation terminate after one attempt.
- [x] Repair the Python reference and remove timing-dependent breaker checks.
  - Acceptance: retries use an explicit contract-approved set; malformed decoding and local/non-retryable request failures are terminal; an injected clock preserves locking and the single-probe invariant; all existing behavior remains green.
- [x] Clarify the main doctrine and failure model; add `references/secure-coding-overlay.md`.
  - Acceptance: retryability follows operation semantics and effect certainty; `policy_limit` remains distinct from saturation; sensitive telemetry is denied by default; every security-sensitive change routes to threat, sink, privilege, data, dependency, and negative-verification controls regardless of tier.
- [x] Strengthen behavioral evals without deleting negative trigger-selection coverage.
  - Acceptance: targeted prompts contain realistic fixtures for effectful reads, saturation versus policy limits, telemetry leakage, concurrency, poison work, rollout compatibility, and security sinks; rubric states observable must/must-not outcomes without canned wording.
- [x] Validate the complete package and independently pressure-test agent usability.
  - Acceptance: reference checks, syntax/CSV checks, skill-creator's `quick_validate.py`, `git diff --check`, current-head diff review, and fresh-agent tests pass; README declares the HTTPX compatibility strategy; remaining risks are recorded below.

## Scope Constraints

- Preserve proportional design: no control without a material failure or security surface.
- Prefer repository, language, framework, and platform facilities over new abstractions or dependencies.
- Keep security detail on demand; `SKILL.md` remains the concise decision entrypoint.
- No commit, push, release, or installed-skill mutation in this task.

## Review

- Outcome: clarified proportional doctrine and the multi-axis failure model, added the on-demand secure-coding overlay, strengthened realistic agent evals, and hardened the illustrative HTTP reference.
- TDD: new regressions failed before fixes for boundary canonicalization, hook mutation, retry classification, deterministic breaker recovery, hostile encodings, and unsafe configuration; all now pass.
- Verified: 43 reference checks on Python 3.11-3.14 with HTTPX 0.28.1 and on Python 3.11 with HTTPX 0.27.0; Ruff, format, mypy, byte compilation, 32-row eval/rubric and AST integrity, package reference integrity, skill validation, optimized-mode fail-closed behavior, and `git diff --check` passed.
- Review: fresh agents correctly handled effectful-read replay and command-injection scenarios; an independent final security review found no remaining actionable issue. Controls were checked against current NIST SSDF 1.1, OWASP ASVS 5.0, CISA Secure by Design, RFC 9110, OWASP logging guidance, and HTTPX documentation.
- Residual and scope: current local changes have not run hosted CI because they were not pushed. TLS, proxy, resolver, custom transport, and access-log policy remain documented caller-owned boundaries. The system-Python validator lacked PyYAML; the isolated validator with PyYAML passed. No commit, push, release, or installed-skill mutation was performed.
