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
