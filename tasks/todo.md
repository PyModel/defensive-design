# Defensive Design 1.6.1 completion ledger (unreleased)

## 1.6.2 maintenance fix

- Main commit `cc61216` failed the hosted latest-HTTPX compatibility job in
  the link-sweep interrupt regression. Its process-wide sleep mock also
  interrupted subprocess reaping. Interrupt injection now targets only the
  sweep's polling seam; the test still uses and reaps a real child.
- The example now rejects HTTPX authentication flows before transport and
  explicitly disables inherited per-request auth. Challenge handling otherwise
  owns its own requests and intermediate response reads. No public result
  types, package paths, or protected check names changed.
- Local verification: 111 unit tests on locked, minimum, and current HTTPX
  using Python 3.12; 60 reference checks; all 18 existing mutants killed.
  This revision does not claim new model evaluations or network-link results.
  Hosted verification is tracked on the change's GitHub checks.

## 1.6.1 and prior work

## Scope and integration — 2026-11-18

Complete the robust, efficient software/system architecture skill and its actual
verification under the user's existing authorization. The earlier 1.6.0 work was
merged through PR #9 while the full experiment was finishing. This follow-up starts
from `main@cc61216a2ddf2f5e6c4afd1abf77c65e2233e70b` on
`improve/defensive-design-verified-1.6.1`. No unrelated work was overwritten.
Historical records below retain their original status; they are not current backlog.

## Completed implementation

- [x] Preserved the task-first Architect / Staff Engineer / Engineering Manager workflow,
  all nine invariant families, architecture-neutral routing and existing public paths.
- [x] Core: 12,093 bytes / 1,403 whitespace words / 191 lines within 12 KiB; compared
  with 1.5.0, `o200k_base` 3,156 → 2,375 and `cl100k_base` 3,178 → 2,388 using
  `tiktoken==0.12.0`. These are encoding counts, not runtime cost/latency measurements.
- [x] Executed all 100 authored scenarios in both skill and no-skill arms, separate
  metadata selection, independent anonymous grading and two actual implementation
  fixtures per arm. Preserved raw answers, grading inputs/maps and all observed failures.
- [x] Refined the three discovered skill omissions: concrete image-converter policy,
  pagination boundary coverage and distinct database statement/lock/idle limits.
- [x] Preserved exact package bytes in validated JSON archives, preventing duplicate
  discoverable skill entrypoints; added archive-integrity and cleanup regressions.
- [x] Strengthened the export task/grader to retain secondary cleanup evidence before
  any export executor ran. All four final fixture solutions passed hidden graders.
- [x] Corrected the cancellation test's shared-clock mock after independent review
  reproduced intermittent failure; preserved production behavior.
- [x] Added CI validation of archived evidence consistency, explicitly without model
  execution or treating historical scores as new behavior evidence.
- [x] Completed the final fresh eight-case check against the exact shipped package:
  8/8 passed with no blocked or critical judgments, after retaining the first 7/8 check.

## Exact evaluation snapshots

| Snapshot | Package SHA-256 | Purpose |
|---|---|---|
| Initial 1.6.0 candidate | `0be52684d55e382887b63f5604e3d3c74f89dba9f71af570d45b47825a677c74` | Complete paired corpus and implementation fixtures |
| First refined candidate | `5708c9c0b799676af83e180c382c338c1a24378c1b2f3363916ae0be658c4db6` | Fresh eight-case check: 7 pass, 1 fail, 0 critical |
| Final 1.6.1 package | `f2ac42b1bd652d43c3f4cdc75c168a4ef909749bd821ceae2a12842c7f4b5509` | Always-loaded collection boundary requirement; fresh check uses these exact bytes |

Digests hash sorted package-relative path, NUL, raw bytes, NUL; generated Python cache
files are excluded. [Release equivalence](../evals/results/1.6.1/release-equivalence.json)
verifies that the final executor snapshot and shipped package have identical bytes.
The first refinement's single-row omission remains visible; moving that requirement
into the core is a behavioral refinement, not relabeling the earlier result.

## Observed evidence

| Check | Result | Scope |
|---|---|---|
| Complete behavior comparison | Skill 97/100; baseline 87/100 | Independent anonymous grading; 0 blocked / 0 critical in each arm; original failures retained |
| First refinement / final package checks | 7/8, then 8/8; 0 critical | Separate fresh conversations and graders; all three originally missed cases pass on the final package |
| Paired outcomes | 86 both pass, 11 skill-only, 1 baseline-only, 2 neither | One completed comparison; cases batched 25 per conversation |
| Metadata selection | TP 78, TN 22, FP 0, FN 0 | Not a native host-router measurement |
| Payment fixture | 7/7 hidden tests in each arm | In-memory, single-process simulation; no real provider durability claim |
| Export fixture | 8/8 hidden tests in each arm | Bounded read/authority/cleanup; no atomic revoke/publish fence in supplied interface |
| `python scripts/validate_skill.py` | verified, passed | Package, 12 KiB, reachability, metadata and corpus structure |
| `python scripts/verify_reference.py` | verified, 60 passed | Deterministic illustrative HTTP example |
| `python -m unittest discover -s tests -v` | verified, 113 passed | Includes archive/schema, one-entrypoint, deadline and link regressions |
| `python scripts/mutation_check.py` | verified, 18/18 killed | Targeted HTTP defensive controls; also passed on exact Python 3.11.18 |
| Ruff / mypy / strict example mypy | verified, passed | Maintained Python code; not semantic grading |
| Compile / pip check / whitespace | verified, passed | Compilation, locked-environment consistency and patch hygiene |
| Cancellation regression repetitions | verified, 20/20 passed | Rechecked after the demonstrated mock repair; independent reviewer also rechecked |
| Archived evidence report | verified, exact recomputation | Complete IDs, exact quotations, snapshot/evidence hashes and stored aggregate |
| Bounded external links | verified run: 61 links, 57 reachable, 0 proven broken, 4 unverified, 44.001 s | Unverified remains explicit; does not prove every URL live |
| Independent final code review | no remaining substantive findings in reviewed delta | Offline review; one reproduced test issue fixed and rechecked |

The [evaluation guide](../evals/README.md) and [complete capture](../evals/results/1.6.1/README.md)
contain raw outputs, exact instructions, fixtures, interruption disclosure, commands
and limits. Local primary verification used Python 3.12.14 with the hash-locked baseline.
Hosted results are assessed at the published follow-up commit, not inferred from the
already-green earlier PR #9 revision.

## New findings and disposition

| ID | Location / trigger | Evidence / impact | Disposition |
|---|---|---|---|
| DD-10 | Full authored corpus previously unrun | Corpus structure alone could not substantiate model behavior or baseline benefit | Closed: all 200 primary responses, 200 independent judgments, 100 selections and four fixture solutions captured |
| DD-13 | Case 30, image converter policy | Generic policy advice did not concretely address dangerous delegates/coders | Fixed and passed in both fresh follow-ups; initial fail retained |
| DD-14 | Archived package under repository | Extra SKILL.md could become an accidentally discoverable installable skill | JSON archive plus exact-integrity and one-entrypoint regressions |
| DD-15 | Cases 66/67, verification and DB controls | Single-row pagination tests and statement/lock/idle limits omitted | Fixed and both pass on the final package; initial fails and the first recheck's repeated pagination omission retained |
| DD-16 | Cancellation regression's shared time.sleep mock | Independent review reproduced second interruption of subprocess reap polling | One-shot interrupt then original sleep; 20 repeats, full suite and independent focused check passed |

The earlier HTTP pool-budget repair, bounded link worker lifecycle, pinned CodeQL,
mutation diagnostics and arbitrary-working-directory discovery are in merged 1.6.0
and are exercised again here. The one earlier mutation baseline failure lacked its
underlying diagnostics; DD-16 is not retroactively asserted to be its cause.

## Evidence boundaries

No known in-scope implementation defect remains open after independent review.
Unavailable host/model variants and actual application integrations are not claimed
as verified. This skill supplies reasoning and engineering procedure, not a deployable
application or universal architecture certification. No production effects, personal
installation, tag or application deployment are implied by repository publication.
Four external URLs remained unverified under the bounded sweep; they were not silently
counted as passes or removed merely to improve the count.

## Historical 1.6.0 record (not current instructions, status or evidence)

# Defensive Design 1.6.0 work ledger (unreleased)

## Current scope — 2026-11-18

User requested completion of the robust, efficient software/system architecture skill,
with no silently deferred work. This revision closes the evaluation, efficiency,
bounded-link-checking, CodeQL, test-import and HTTP deadline gaps from earlier records.
Repository development and authorized GitHub publication are tracked separately from
application deployment, which is not applicable to this Markdown skill.

Base: `main@7197f50057dc69073dda4903f2261cb858a9e844` (merged 1.5.0).
Work branch: `improve/complete-defensive-design-2026-11-18`.
Earlier records are preserved as historical evidence, not current instructions or status.

## Implemented

- [x] Task-first core with all nine invariant families and existing references retained:
  11,947 bytes / 1,385 words / 189 lines, versus 16,097 / 2,121 / 236.
- [x] Exact named-encoding token measurements outside runtime dependencies:
  `tiktoken==0.12.0`, `o200k_base` 3,156 → 2,346; `cl100k_base` 3,178 → 2,358.
  These are encoding-specific counts, not a host runtime cost/latency measurement.
- [x] New 12 KiB maintenance budget to prevent core context growth.
- [x] Model-independent snapshot/evidence harness with strict schemas, exact case
  coverage, verbatim grading evidence and honest blocked/failed denominators.
- [x] Separate payment recovery and object-authorization implementation fixtures;
  buggy starters fail their hidden checks before any agent repairs them.
- [x] Bounded concurrent external-link checking, explicit unverified outcomes,
  process cleanup and JSON evidence; 14 new offline regressions.
- [x] Pinned Python CodeQL security-extended workflow with minimal upload permissions.
- [x] Expired/retried HTTP pool acquisition fix and two deadline regressions;
  an added targeted mutant verifies the remaining-budget guard.
- [x] Test-package discovery from arbitrary working directories with `-s` and `-t`;
  no per-file import-path hacks or new application dependencies.

## Current verification

The final package snapshot SHA-256 is
`0be52684d55e382887b63f5604e3d3c74f89dba9f71af570d45b47825a677c74`.
This hashes sorted package-relative path, NUL, raw content, NUL, excluding generated
`__pycache__`. Model evaluation uses this exact snapshot. The baseline receives no
skill instructions; raw corpus inputs contain no expected selection or grading text.

Execution evidence and dispositions are being completed for this revision. The final
record distinguishes model judgments, executable fixture assertions, offline repository
checks, live links and hosted CI. A single host/model experiment cannot establish
universal superiority; no broader performance claim is implied.

## Findings and disposition

| ID | Location / trigger | Evidence and impact | Status |
|---|---|---|---|
| DD-08 | HTTP retry enters pool acquisition after most of operation budget is spent | Before fix, configured pool wait was 0.2 s while less than 0.1 s remained; operation expired and local saturation could be charged to upstream breaker | Fixed: remaining-budget cap, no-I/O expiry guard, executable regressions and mutant |
| DD-09 | Serial external link checker encounters slow DNS/network | Prior 120 s invocation produced no complete report; urllib timeout did not cover whole-run/DNS behavior | Fixed: process isolation and bounded sweep, full classifications preserved |
| DD-11 | New pool regression mixed a fake clock jump with a real sleep | First hosted latest-HTTPX canary expired under runner scheduling while other jobs passed | Fixed test to advance the controlled monotonic clock by the transport wait; removed wall-clock dependence without weakening guard/outcome assertions |
| DD-10 | 100 authored cases were treated only as a structure-valid corpus | No complete trigger/behavior/baseline evidence or implementation fixture existed | Harness and fixtures implemented; full experiment evidence recorded below when executed |

## Historical 1.5.0 record (not current instructions, status or evidence)

# Defensive Design 1.5.0 work ledger (unreleased)

## Current scope — 2026-11-18

User request: inspect and refine `PyModel/defensive-design` into broadly applicable,
production-ready architecture and engineering guidance, enforcing error/edge-case
handling, bounded repeat-safe retries, security and shipping rigor. This is repository
development; no personal skill installation, merge, tag, release or deployment is part
of this change. Preserve the portable package, existing public paths and HTTP example.

Base: `main@31cd5f676f3eac4f64ce76f18088198efaf815cc` (1.4.0).
Work branch: `improve/production-architecture-2026-11-18`.
Reviewable publication: branch and draft pull request; saved Git state is reported
separately from package or application readiness. Earlier records below are historical,
not current authority, status or evidence.

## Completed

- [x] Inspected the existing core, all references, package/CI contracts and evaluation setup.
- [x] Added architecture decisions and interface contracts as on-demand references;
  retained the core at 236 lines and 16,097 bytes, below the existing 16 KiB limit.
- [x] Added explicit architect/staff/manager responsibilities, pre-implementation
  assumptions, tradeoffs, blast radius, compatibility, observability and ownership.
- [x] Expanded security lifecycle, bounded recovery, service objectives, rollout,
  schema migration, restore/failover and operational ownership guidance.
- [x] Fixed the guidance and offline test findings below; preserved HTTP example code,
  result types, dependency locks, workflows and existing protected CI check names.
- [x] Added 23 prompt/rubric pairs (18 positive, 5 negative); total 100, with 22 negative.
- [x] Updated source/applicability mappings, assessment template, adapter metadata,
  README, changelog, maintenance guide and public-path/count checks.
- [x] Forward-tested nine distinct design scenarios with fresh isolated subagents;
  clarified one partial restore response and rechecked it in a new conversation.
- [x] Independent read-only review found no substantive guidance or compatibility
  defect; resolved its missing-ledger observation and corrected an evaluation wording
  overclaim to distinguish instructed directory scope from enforced access isolation.

## Findings and disposition

Severity below describes the potential consequence of following guidance, not a claim
that the skill repository or a production application contains that runtime defect.

| ID / severity | Location and trigger | Impact and evidence | Status |
|---|---|---|---|
| DD-01 / High | Failure taxonomy, capacity checklist and test catalogue: drop work on deadline/TTL/lease expiry | A payment can be committed or unknown after an attempt expires; source text did not preserve the business obligation | Fixed across core/taxonomy/checklists/rollout; sampled cases 85 and 92 preserve identity and reconcile |
| DD-02 / High | Idempotency checklist: reservation/key expiry with uncertain external effect | Expiry could be read as permission to admit a new effect | Explicitly forbid fresh effects until noncommit or repeat safety is established; no application runtime claim |
| DD-03 / Medium | Authorization checklist: apply user authorization unchanged to every replay/recovery | Revoked delegation and an accepted service obligation need different execution policy | Preserved authority invariants with scoped operation-specific policy; case 86 passed |
| DD-04 / Low | Concurrency/shutdown wording: lock timeout prevents deadlock; readiness immediately stops traffic | Timeout only bounds waiting; existing connections and routing propagation can continue | Corrected mechanisms and recovery expectations |
| DD-05 / Medium | `tests/test_fuzz_boundaries.py`, URL-only property test, inherited SOCKS proxy | Baseline ran 72 tests with one ImportError before URL assertions because optional socksio was absent | Reproduced before fix; set `trust_env=False` only on the no-I/O test client; all 72 now pass |
| DD-06 / Low | README CI range ended at 3.14 while existing workflow includes 3.15 | Documented supported matrix differed from configuration | Updated README range; workflow unchanged |
| DD-07 / Medium | Sample restore response omitted secondary recovery gates | Payment reconciliation alone did not state authority/privacy, keys/config and capacity checks | Replaced the restore preflight paragraph with an explicit applicability matrix; same scenario passed fresh recheck |

Architecture choice, API/event evolution, OAuth/session lifecycle, build trust and
operations ownership were coverage gaps, not demonstrated application vulnerabilities.
Their new decision tables remain proportional and do not mandate a particular stack.

## Verification evidence

Environment: Python 3.12.14 in an isolated venv installed with
`python -m pip install --require-hashes -r requirements-dev.txt`; `python -m pip check`
passed. The commands below used that venv. Results are newly executed for 1.5.0, not
reused from historical records.

| Command | Result | Scope / limitation |
|---|---|---|
| `python scripts/validate_skill.py` | verified, passed | Metadata, 16 KiB budget, local links/reachability, adapter and 100-case corpus structure |
| `python scripts/verify_reference.py` | verified, 60 passed | Deterministic illustrative HTTP reference behavior |
| `python -m unittest discover -s tests -v` | verified, 72 passed | Validator, public surface, seeded properties and deadline regressions |
| `python scripts/mutation_check.py` | verified, 17/17 killed | Existing targeted reference controls; not model behavior |
| `python -m ruff check scripts skills tests` | verified, passed | Repository Python lint |
| `python -m mypy scripts tests` | verified, passed | 8 source files |
| `python -m mypy --strict skills/defensive-design/references` | verified, passed | 1 illustrative Python source file |
| `python -m compileall -q scripts skills tests` | verified, passed | Python compilation |
| `git diff --check` | verified, passed | Patch whitespace |
| Bundled skill-creator `quick_validate.py` on baseline and revision | verified, both reject `compatibility` | Helper schema omits this existing optional field; the current Agent Skills specification allows it and the repository validator passes. Preserved valid metadata rather than weakening it for an older helper. |
| `timeout 120s python -u -m scripts.check_links` | blocked, exit 124 | Complete external URL sweep exceeded the bounded execution window without a summary; no complete reachability pass is claimed |

The final package content digest is
`65c393ca32d123c30b637ce153b60d88f38f67774352738274997ad3168bec6a` (SHA-256 of
sorted relative file path, NUL, raw file content, NUL; generated `__pycache__` excluded).
The host interface was generated with the skill-creator helper and the existing
implicit-invocation policy retained. Source-ledger additions were completed after the
initial behavior sample; the only later behavioral change was the restore gate matrix,
which received the fresh case-92 recheck.

Behavior sample: ChatGPT Work / GPT-6 Astra Pro, exact build not exposed; three fresh
agents answered three raw scenarios each from an isolated skill copy. Initial result:
8 full matches and 1 partial (case 92). After clarifying restore gates, a fourth fresh
agent answered the same raw case and matched the rubric. Nine distinct cases, ten
responses, author-graded; no no-skill baseline or trigger measurement. The
[evaluation record](../evals/README.md) lists cases and observable outcomes.

## Remaining verification boundaries

- `reasoned_not_run`: the complete 100-case corpus, negative trigger accuracy,
  cross-host/model generalization and implementation-mode application fixtures.
- Local execution used Python 3.12.14; other matrix versions and dependency canaries
  require their own hosted execution evidence. A workflow definition is not a pass.
- Primary sources were read through web retrieval; external reachability checks are
  separate from factual review and local-link validation.
- No application integration/load/production test, installation, deployment, tag or
  release occurred. No claim of certification or exhaustive architecture coverage.
- Historical CodeQL/harness/tag decisions remain historical backlog; this change
  neither resolves them nor treats them as prerequisites for using the Markdown skill.

## Historical 1.4.0 record (not current instructions, status or evidence)

The following original record is preserved for traceability. Its authorization,
uncommitted-work statements, counts and verification dates describe that earlier work.

### Defensive Design 1.4.0 work ledger (unreleased)

## Scope

User request (2026-11-10): audit the skill for weaknesses, then "apply all" findings.
Branch `improve/robustness-audit-2026-11` from `main@e9c9c0f`. Changes are uncommitted;
no commit, push, tag, release or model-evaluation spend was authorized.

## Completed

- [x] HTTP example: pool saturation misreported as `UPSTREAM_TIMEOUT` under the default
  configuration (regression failed before the fix); over-limit Retry-After returned to
  the caller; the deadline-bound retry exit logs.
- [x] Four new reference checks and four new mutants; `mutation_check.py` handles a hung
  or non-compiling mutant.
- [x] Validator: git-tracked docs only, single error for missing PyYAML or bad YAML,
  named fields and reasons, empty body, hidden format characters, version to CHANGELOG
  tie, no host paths. Ten new tests; nine were seen failing before their fix.
- [x] Guidance: see CHANGELOG 1.4.0. `SKILL.md` is 14,927 of 16,384 bytes.
- [x] 14 evaluation cases with rubric rows (77 total, 17 negative, 22%).
- [x] CI: Python 3.15, weekly `verify`, weekly `links`. Doc counts pinned by a test.

## Not done (with reason)

- `blocked`: the 77-case corpus is still unrun as a corpus. `claude plugin eval` is
  present locally (2.1.322) with a no-plugin baseline arm and `--max-cost-usd`, but it
  reads `case.yaml` or `prompt.md` plus graders from an eval directory below the
  target, not this CSV and rubric. Converting the cases, deciding where that directory
  lives given that evals are never packaged, and the spend are owner decisions.
  Whether a plugin manifest is required was not verified (`reasoned_not_run`).
- `blocked`: no tag or release exists for any version. Publishing is outward-facing and
  was not authorized. CHANGELOG says `1.4.0 - unreleased`; set the date when tagging.
- Not changed, by choice: `verification-and-chaos.md` keeps its file name (a documented
  package path); `RemoteProtocolError` stays terminal (tested as intended).
- The new trigger words in the description are a hypothesis until trigger evals run.
- Fixture repositories, implement-mode and long-context evaluation cases were not added;
  they need the eval harness decision above.
- Earlier open items stand: CodeQL setup, the token estimate, the test import path.

## Verification evidence

`verified` locally on 2026-11-10, hash-locked venvs. Python 3.13.11: `validate_skill.py`,
`verify_reference.py` (60 checks), unittest (72 tests), `mutation_check.py` (17 of 17
killed), Ruff, mypy, strict mypy on the example, compileall, `git diff --check`, and
`python -m scripts.check_links` (30 links, 0 broken). Python 3.15.2: validator, 60
checks, 72 tests, Ruff, mypy. A loopback repro with a one-connection pool returned
`UPSTREAM_TIMEOUT` before the fix and `LOCAL_POOL_TIMEOUT` after it.
`reasoned_not_run`: hosted CI, including the new 3.15 job (a uv dry run resolved the hash
lock for Linux x86-64 on 3.15) and both scheduled workflows. The HTTPX 0.27.0 path passed
on Python 3.11.14 (validator, 60 checks, 72 tests).

`verified` sample behavior: one fresh Claude Opus subagent (this host, 2026-11-10) answered
cases 64, 67, 68, 70 and 71 from the skill alone, without access to `evals/`. All five
matched their rubric rows. This is a five-case sample graded by the author of the
cases, not a corpus pass, and it does not test triggering. `blocked`: the full corpus.

Jev `gate_range` on the final diff verified 7 of 7 claims, but its patch review escalated
(safe_to_apply 0.71, composite 0.695, below the 0.8 auto threshold; test-gap was its
lowest score). The packaged-file diff was then read in full. Open, not fixed: an
operation deadline that expires during a pool wait is still charged to the breaker.

---

## Historical record: assurance hardening, 2026-11-02 (not current task instructions or new evidence)

## Scope

Pasted external review (2026-11-02) of `main@97e6479` recommending 14 assurance
enhancements. Implemented the in-repo items with real failure surfaces; nothing under
`skills/defensive-design/` changed, so no version bump. On user instruction the work was
merged to `main` through PR #4 (rebase), followed by the first Dependabot actions PR #5.
No release was made.

## Completed

- [x] F1 `verified`: locked `certifi` 2026.7.22 had PYSEC-2026-4320 (pip-audit 2.10.1).
  Raised to 2026.10.23 with `--upgrade-package` (PR #4 review: 2026.10.18 dropped
  all four emSign roots; counted in each wheel: 10.19 has 3, 10.23 has 1); no other pin changed.
- [x] F2 `verified`: Dependabot alerts were on but covered nothing. GitHub's dependency
  graph returned zero manifests because it only reads `requirements.txt`. Added the
  `audit` workflow (push, PR, weekly); new check name, existing names untouched.
- [x] Seeded stdlib property tests (`tests/test_fuzz_boundaries.py`, 10 tests) and a
  public-surface pin (`tests/test_public_surface.py`, 2 tests). A hand mutation run
  removed each guarded property in turn: 9 of 9 detected, after adding explicit
  dot-segment seeds for the one survivor. PR #4 review added exact-value checks for
  valid digit headers; 2 of 2 new mutants detected.
- [x] `SECURITY.md`; Dependabot version updates for workflow actions only.
- [x] Follow-up branch `fix/hash-lock-auditor`: the `audit` job installed `pip-audit`
  with unpinned transitive dependencies. It now installs from its own hash lock
  (`requirements-audit.txt`) and audits both locks.
- [x] Keep-alive for the weekly audit schedule: merge the weekly Dependabot actions PRs
  (user choice, 2026-11-02). Making the audit a required check was declined.
- [x] Repository settings changed on 2026-11-02, all reversible: private vulnerability
  reporting, secret scanning and secret push protection set to enabled.

## Not done (with reason)

- `blocked`: automated agent-behavior evals in CI need model API secrets and a budget
  decision. The full 63-case corpus is still unrun.
- `not_applicable`: release provenance and attestations, because no releases exist.
- Declined as disproportionate for one maintainer and about 3k lines of Python:
  Hypothesis and pytest (a seeded stdlib generator covers the same properties with no
  new dependency), CONTRIBUTING (AGENTS.md covers it), CODEOWNERS, generic mutation
  testing, pre-commit, coverage gates, perf benchmarks, Bandit, Semgrep and an SBOM.
- Open, user decision: CodeQL default setup (`not-configured`).
- Dependabot for pip was left out on purpose. It is not verified to regenerate the `.in`
  file and the uv hash lock together, so Python pins stay manual.

## Verification evidence

`verified` locally on 2026-11-02 with hash-locked venvs on Python 3.11.14, 3.12.14,
3.13.11 and 3.14.9 for the first PR #4 commit. All of these passed on each version:
`validate_skill.py`, `verify_reference.py` (56 checks), unittest (59 tests), Ruff, mypy,
strict mypy and compileall. The review-fix commit (60 tests) was rerun locally on 3.11
only; hosted CI passed all four versions on it and on `main` after each merge. `uv pip check` also passed. On 3.11, `mutation_check.py` killed 13 of 13
mutants. `pip-audit --require-hashes --disable-pip` found no known vulnerabilities.
`git diff --check` passed. The HTTPX 0.27.0 path also passed on 3.11 (validator, 56
checks, 59 tests). Jev `gate_range` verified every claim, but its patch review
escalated at safe_to_apply 0.77 with correctness confidence 0.19. The diff was then
read in full. `verified` hosted: the `audit` workflow passed on PR #4, PR #5 and `main`;
the first Dependabot PR (#5) had its pinned SHAs matched to upstream tags before merge.

---

## Historical 1.3.0 record (not current task instructions or new evidence)

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
