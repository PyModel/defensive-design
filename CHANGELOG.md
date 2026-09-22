# Changelog

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
