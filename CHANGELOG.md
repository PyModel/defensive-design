# Changelog

## 1.4.0 - unreleased

### Added (skill guidance)

- `SKILL.md`: a default or fallback that replaces a failure is a finding; new code matches
  its siblings' guards and names only symbols, keys and packages that exist; the agent's
  own timed-out commands are unknown outcomes, and a repeated failed repair stops. The
  description names its trigger topics and `compatibility` states the example's runtime.
- `references/code-level-design.md`: detached-task errors, cleanup that masks the original
  error, reporting a failure once, daylight-saving and clock-skew cases, collections and
  paging, and a section on shell scripts and CI steps.
- `references/failure-taxonomy.md`: transport phase decides `not_started` versus
  `unknown_outcome`.
- `references/defensive-checklists.md`: shared retry budget, non-replayable requests,
  database timeouts, isolation level and whole-transaction retry, unobserved background
  failures, and four model-boundary items.
- `references/verification-and-chaos.md`: a test-integrity section.
- `references/secure-coding-overlay.md`: sibling entry-point guards.
- `assets/assessment-template.md`: a four-level severity scale.
- A contents line in every reference longer than 100 lines; two source rows.
- 14 evaluation cases (11 positive, 3 negative) and four cross-cutting graders.

### Fixed (illustrative HTTP example)

- With the default configuration the pool wait and the per-attempt timer were equal, and
  the per-attempt timer fired first. Local pool saturation was reported as
  `UPSTREAM_TIMEOUT` and charged to the breaker. The default pool timeout is now half the
  per-attempt timeout, and an explicit `pool_timeout_s` must be below it.
- A Retry-After above `max_retry_after_s` was dropped. The result now carries the
  server's value in `retry_after_s` with `RETRY_AFTER_EXCEEDS_BUDGET`; automatic retry
  still stops.
- The exit taken when a retry wait cannot fit the deadline now logs, like retry exhaustion.

### Maintenance

- Reference checks grew from 56 to 60 and targeted mutants from 13 to 17. The new ones
  cover the backoff cap, the stale failure permit, the declared-length fast path and the
  pool default. `mutation_check.py` treats a hung mutant as detected and rejects a mutant
  that does not compile.
- Validator: repository docs come from the git-tracked set; a missing PyYAML or
  unparseable frontmatter is one error; unknown fields and invalid names are named; an
  empty body, hidden format characters and a version without a CHANGELOG section are
  rejected; read errors no longer print host paths. Validator tests grew from 44 to 54.
- `tests/test_public_surface.py` pins the counts quoted in README and the evaluation guide.
- CI: Python 3.15 in the matrix, a weekly `verify` run, and a weekly `links` workflow
  (`scripts/check_links.py`).

### Compatibility

Skill name, install command, package paths and `FetchStatus` values are unchanged.
Observable changes in the example: the default pool timeout is half
`per_attempt_timeout_s`; `pool_timeout_s >= per_attempt_timeout_s` raises `ValueError`
(equality was accepted before); `retry_after_s` is set on `RETRY_AFTER_EXCEEDS_BUDGET`
results when the header parsed.

The entries below were made earlier in this cycle and touch maintainer tooling only.

### Security

- The locked `certifi` 2026.7.22 had PYSEC-2026-4320. Raised to 2026.10.23,
  the latest release; no other pin changed. The first fixed release, 2026.10.18,
  dropped all four emSign roots; 2026.10.19 restored three and 2026.10.23 keeps one.

### Added

- `audit` workflow: `pip-audit` on `requirements-dev.txt` on push, pull request and
  weekly. GitHub's dependency graph only reads `requirements.txt`, so Dependabot alerts
  were covering none of the locked packages.
- `requirements-audit.txt`: a separate hash lock for `pip-audit`, so the audit job no
  longer resolves the auditor's dependencies unpinned.
- Dependabot version updates for the pinned workflow actions. Python pins stay manual
  because the `.in` file and its hash lock must be regenerated together.
- `SECURITY.md` with private reporting through GitHub security advisories.
- `tests/test_fuzz_boundaries.py`: seeded generative property tests for Retry-After,
  Content-Length, display text, user-ID path segments, domain canonicalization, JSON
  depth, the Markdown helpers and local-link confinement. Each property was checked
  against a deliberate defect (11 of 11 detected), including exact values for
  valid ASCII-digit Retry-After and Content-Length headers.
- `tests/test_public_surface.py`: pins the 12 package paths and the `FetchStatus`
  names and values.

## 1.3.0 - 2026-09-22

### Changed (layout)

- The installable package moved to `skills/defensive-design/`. The `skills` CLI copies
  every file of a skill directory except `.git`, `__pycache__`, `__pypackages__` and
  `metadata.json`, so the previous root layout installed evaluation rubrics, tests,
  CI and historical work ledgers with the skill. The install command, skill name and
  every package-relative path are unchanged. `SKILL.md` no longer links the maintainer
  evaluation corpus.

### Added

- `references/code-level-design.md`: invariant ownership by level (function, type,
  module, process, store, distributed system), programmer errors versus invalid input,
  assertions that disappear in optimized builds, parsing once at the boundary,
  exhaustive state handling, resource ownership, in-process and `await` races, and
  numeric, time and text pitfalls. Language claims cite primary documentation.
- `contract_violation` cause in the failure taxonomy.
- Surface-to-reference routing table in `SKILL.md`, replacing tier-only routing prose.
- 15 evaluation cases: 9 positive and 3 negative across Go, Rust, TypeScript, Java, C,
  Python and Kubernetes, plus 3 near-miss negatives; paired rubric rows and two
  cross-cutting graders.

### Fixed (illustrative HTTP example)

- A Retry-After hint longer than the remaining deadline slept through the whole budget
  and discarded the hint. The example now stops and returns the hint.
- `per_attempt_timeout_s` bounded each socket operation, so a slow-dripping server held
  an attempt until the operation deadline. Each attempt now has a total bound.
- Attempts cut off by the operation deadline never counted as breaker failures.
- Invalid payloads and unexpected 2xx/3xx responses reset the breaker's failure count.
- Local pool saturation during a probe restarted the dependency's cooldown.
- A breaker opened by the call's own retries masked their cause as `CIRCUIT_OPEN`.
- Deep JSON relied on `RecursionError`, which CPython 3.14 no longer raises for the
  tested depth. Nesting is now bounded explicitly (`JSON_TOO_DEEP`).
- Leading zeros in Retry-After, permissive Content-Length parsing, and bidi, zero-width
  and separator characters in display text.
- Configuration now rejects a per-attempt budget above the deadline and phase timeouts
  above the per-attempt budget. The unreachable `DecodingError` branch was removed.
- `sleep` and `uniform` are injectable instead of patched process-wide in tests.

### Maintenance

- Validator: orphan packaged files, reference-style/HTML/angle links, unclosed fences,
  inline code and setext headings, duplicate prompts, rubric polarity, a 20% negative
  floor, the Codex `agents/openai.yaml` schema, Claude reserved-name and XML-tag rules,
  and a packaged LICENSE copy.
- Validator also checks local links in repository docs outside the package.
- Reference checks grew from 43 to 56 and are auto-collected. New
  `scripts/mutation_check.py` removes each of 13 controls in turn and fails on any
  survivor (runs in CI on Python 3.11). Validator tests grew from 30 to 44.
- CI installs a universal hash-locked baseline, runs Ruff and mypy (strict for the
  example), checks whitespace against the empty tree, and no longer cancels runs on main.
- Knowledge moved, not dropped: failure-path tests live in the verification reference;
  the duplicate evidence-state table points to `SKILL.md`. The broken OWASP ASVS link
  and the moved OpenAI skills documentation link were updated.

### Compatibility

Skill name, install command and package-relative paths are unchanged. Repository-level
paths gained the `skills/defensive-design/` prefix. No application migration is required.

Observable changes in the illustrative HTTP example (`FetchStatus` values unchanged):

- New `error_code` `JSON_TOO_DEEP` for nesting above `MAX_JSON_DEPTH` (32).
- When the call's own failures open the breaker, the result carries their cause and
  Retry-After hint instead of `CIRCUIT_OPEN`.
- A retry wait that cannot finish before the deadline returns `TEMPORARILY_UNAVAILABLE`
  with the hint instead of `CANCELLED`/`DEADLINE_EXCEEDED`.
- An attempt slower than `per_attempt_timeout_s` in total is now cut off and retried,
  even if every individual socket read was fast.
- Configurations with `per_attempt_timeout_s > deadline_s`, or connect/pool timeouts
  above `per_attempt_timeout_s`, now raise `ValueError`.
- Display names containing format (bidi, zero-width) or line/paragraph separator
  characters are rejected as `INVALID_DISPLAY_NAME`.
- Content-Length values that are not plain ASCII digits (`+5`, `1_0`) are ignored and
  the body is read under the streaming cap; Retry-After ignores leading zeros.
- Breaker accounting: invalid payloads and unexpected 2xx/3xx are neutral, deadline-cut
  attempts count as failures, and local pool saturation keeps the existing cooldown.
- New keyword-only `sleep` and `uniform` parameters with standard defaults.

## 1.2.0 - 2026-09-04

### Fixed

- The illustrative HTTP client could return success when synchronous parsing or response
  cleanup crossed the operation deadline before the event loop ran its cancellation
  callback. Use the event-loop deadline and check completion time before returning.
  The deadline remains cooperative, not hard real-time preemption.
- Replace blanket rejection of process-local synchronization with state-ownership scope.
- Apply timeout, queue, distributed-state and recovery checks only to actual surfaces.
- Permit explicit low-risk audits and recognize consequential pure computation.

### Added

- Architecture/capability adaptation, optional assessment template and primary-source map.
- Explicit review/design/implementation/incident modes and action-authority boundaries.
- Local, offline, UI, stream, data, infrastructure, device and agent evaluation cases.
- Offline package validation and negative tests; preserve the existing trigger corpus.
- Read-only, pinned-action CI with a reviewed dependency baseline, separate HTTPX
  compatibility checks, bounded runtime and source/environment evidence artifacts.
- Maintenance guidance and distinct package/example/model-evaluation evidence rules.

### Compatibility and limitations

The skill name, existing reference paths and public example result types are retained.
Install the complete package. No application dependency or data migration is required.
Python dependencies are for maintainers and the optional example only. Package checks
and deterministic regressions do not prove autonomous behavior on every codebase.
See README for rollout and rollback, and tasks/todo.md for the current evidence record.
