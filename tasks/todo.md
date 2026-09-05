# Defensive Design 1.2.0 work ledger

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
