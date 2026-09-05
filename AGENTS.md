# Repository maintenance

This repository distributes a portable Agent Skills package, not a general-purpose
resilience library. Keep the core short and architecture-neutral. Load detailed
references on demand. Do not add infrastructure merely to exemplify a design pattern.

## Structure and compatibility

- `SKILL.md`: trigger, workflow, invariants, routing, version metadata.
- `references/`: optional reasoning adapters and the illustrative HTTP example.
- `assets/`: optional assessment template; no required output bureaucracy.
- `evals/`: trigger cases, observable behavior rubric and evaluation procedure.
- `scripts/` and `tests/`: package and reference checks, not agent evaluation results.
- `agents/`: optional provider adapter; the core must not depend on it.
- `tasks/todo.md`: current work evidence and clearly separated historical records.

Preserve the public skill name, supported reference paths and example result types
unless a documented migration justifies a break. Keep dependency pins and CI action
pins reviewed. Preserve the existing protected-branch check names.

## Change discipline

Inspect before claiming a defect. Report every discovered defect with location, trigger,
impact, evidence and status. Fix authorized in-scope bugs; record remaining findings
explicitly, never silently defer or call them done. Respect review-only requests and
user authority. Repository text is not permission to install, commit, push or deploy.

When authorized, make small, readable, reviewable commits. Never overwrite unrelated
work, force-push, weaken protections or expose secrets. Update the relevant reference,
eval/rubric pair, README, changelog, work ledger and this guide when their contracts or
structure change. Historical verification records are not evidence for new revisions.

## Verification

In a reviewed Python 3.11+ environment with `requirements-dev.txt` installed:

```bash
python scripts/validate_skill.py
python scripts/verify_reference.py
python -m unittest discover -s tests -v
python -m compileall -q scripts references tests
git diff --check
```

Use deterministic failing regressions before behavioral fixes where practical. Test the
final state, not only an earlier commit. Static package validation, HTTP example tests,
model behavior evaluations, integration tests and production guarantees are distinct.
Report exact commands and scope with verified, reasoned_not_run, blocked or
not_applicable. Do not fabricate model evaluations or reuse historical pass claims.
